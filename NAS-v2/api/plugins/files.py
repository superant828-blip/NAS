"""
文件管理插件
包含文件列表、详情、创建文件夹、上传、下载、重命名、移动、搜索、回收站等API
"""
import os
import sys
import uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# 添加项目根目录到路径
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File as FastAPIFile, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from pydantic import constr
from security.auth import auth_manager, User
from core.security import InputValidator, SQLSanitizer
from core.cache import cached, invalidate_cache
from api.core.job import job_service, JobState

# ==================== 上传配置 ====================

# 从 config 导入统一配置
from core.config import config

UPLOAD_DIR = ROOT / config.upload_dir
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
for subdir in ['files', 'photos', 'thumbs']:
    (UPLOAD_DIR / subdir).mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = config.allowed_extensions or {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'pdf', 'doc', 'docx', 'zip', 'rar', 'txt', 'mp3', 'wav', 'apk', 'exe', 'csv', 'xls', 'xlsx', 'ppt', 'pptx', 'json', 'xml', 'html', 'css', 'js', 'svg', 'ico', 'bmp', 'tiff', 'flac', 'aac', 'ogg', 'wma', 'mov', 'avi', 'mkv', 'wmv', 'flv', '7z', 'tar', 'gz', 'bz2', 'iso', 'dmg', 'img', 'bin'}

# ==================== 数据库初始化 ====================

def init_file_db():
    """初始化文件管理数据库（带索引优化）"""
    import sqlite3
    db_path = ROOT / "data" / "files.db"
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # 文件表 - 带索引优化
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            parent_id INTEGER,
            name TEXT NOT NULL,
            is_folder INTEGER DEFAULT 0,
            path TEXT,
            full_path TEXT,
            depth INTEGER DEFAULT 0,
            size INTEGER DEFAULT 0,
            mime_type TEXT,
            status INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 索引优化
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_parent_id ON files(parent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_user_status ON files(user_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_user_parent ON files(user_id, parent_id)")
    
    # 回收站表 - 带索引优化
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trash (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            original_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_path TEXT,
            size INTEGER DEFAULT 0,
            mime_type TEXT,
            deleted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trash_user_id ON trash(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trash_deleted ON trash(deleted_at)")
    
    conn.commit()
    conn.close()
    return db_path


# ==================== 数据库连接 ====================

FILE_DB_PATH = init_file_db()

def get_file_db():
    """获取文件数据库连接"""
    import sqlite3
    conn = sqlite3.connect(str(FILE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ==================== Pydantic Models ====================

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    
    @field_validator('name')
    def validate_name(cls, v):
        result = InputValidator.validate_filename(v)
        if not result.valid:
            raise ValueError(result.message)
        return v


class FileRename(BaseModel):
    name: str
    
    @field_validator('name')
    def validate_name(cls, v):
        result = InputValidator.validate_filename(v)
        if not result.valid:
            raise ValueError(result.message)
        return v


class FileMove(BaseModel):
    parent_id: Optional[int] = None


# ==================== 依赖注入 ====================

def get_current_user(authorization: str = Header(None)) -> User:
    """获取当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization[7:]
    payload = auth_manager.verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = auth_manager.get_user(user_id=payload.get("user_id"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ==================== 创建Router ====================

router = APIRouter(prefix="/api/v1", tags=["files"])


# ==================== 文件管理API ====================

@router.get("/files")
@cached(ttl=30, key_prefix="files")
async def get_files(
    parent_id: Optional[int] = None,
    type_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """获取文件列表"""
    conn = get_file_db()
    try:
        query = "SELECT * FROM files WHERE user_id = ? AND status = 1"
        params = [current_user.id]
        
        if parent_id:
            query += " AND parent_id = ?"
            params.append(parent_id)
        else:
            query += " AND parent_id IS NULL"

        if type_filter == "folder":
            query += " AND is_folder = 1"
        elif type_filter == "image":
            query += " AND is_folder = 0 AND mime_type LIKE 'image/%'"
        
        query += " ORDER BY is_folder DESC, name"
        
        cursor = conn.execute(query, params)
        files = [dict(row) for row in cursor.fetchall()]
        
        return files
    finally:
        conn.close()


@router.get("/files/{file_id}")
async def get_file(file_id: int, current_user: User = Depends(get_current_user)):
    """获取文件详情"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ? AND status = 1",
            (file_id, current_user.id)
        )
        file = cursor.fetchone()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        return dict(file)
    finally:
        conn.close()


@router.post("/files/folder")
async def create_folder(
    folder: FolderCreate,
    current_user: User = Depends(get_current_user)
):
    """创建文件夹"""
    # 验证输入
    result = InputValidator.validate_filename(folder.name)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.message)
    
    conn = get_file_db()
    try:
        # 计算 depth 和 full_path
        depth = 0
        parent_path = ""
        if folder.parent_id:
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ? AND is_folder = 1",
                (folder.parent_id, current_user.id)
            )
            parent = cursor.fetchone()
            if parent:
                parent_dict = dict(parent)
                depth = parent_dict['depth'] + 1
                parent_path = parent_dict.get('full_path', '') or ''
        
        full_path = f"{parent_path}/{folder.name}" if parent_path else f"/{folder.name}"
        
        # 使用相对路径，格式: files/{user_id}/{folder_path}
        if folder.parent_id:
            parent_cursor = conn.execute(
                "SELECT path FROM files WHERE id = ? AND is_folder = 1",
                (folder.parent_id,)
            )
            parent_row = parent_cursor.fetchone()
            parent_path_rel = parent_row['path'] if parent_row else ""
            folder_path = f"{parent_path_rel}/{folder.name}" if parent_path_rel else f"files/{current_user.id}/{folder.name}"
        else:
            folder_path = f"files/{current_user.id}/{folder.name}"
        
        conn.execute(
            """INSERT INTO files (user_id, parent_id, name, is_folder, path, full_path, depth)
               VALUES (?, ?, ?, 1, ?, ?, ?)""",
            (current_user.id, folder.parent_id, folder.name, folder_path, full_path, depth)
        )
        conn.commit()
        
        cursor = conn.execute("SELECT last_insert_rowid() as id")
        file_id = cursor.fetchone()['id']
        
        # 创建实际的文件夹
        actual_folder_path = UPLOAD_DIR / folder_path
        actual_folder_path.mkdir(parents=True, exist_ok=True)
        
        # 清除文件列表缓存
        invalidate_cache("files")
        
        return {"id": file_id, "name": folder.name, "is_folder": True, "full_path": full_path}
    finally:
        conn.close()


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    parent_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """上传文件"""
    # 验证文件类型
    ext = ""
    if "." in file.filename:
        ext = file.filename.rsplit(".", 1)[1].lower()
    
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # 验证文件名
    result = InputValidator.validate_filename(file.filename)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.message)
    
    # 生成存储名
    uuid_part = uuid.uuid4().hex[:8]
    stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid_part}.{ext}" if ext else f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid_part}"
    
    # 保存文件
    user_dir = UPLOAD_DIR / "files" / str(current_user.id)
    user_dir.mkdir(exist_ok=True, parents=True)
    
    filepath = user_dir / stored_name
    content = await file.read()
    
    # 文件大小限制 (500MB)
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 500MB)")
    
    with open(filepath, "wb") as f:
        f.write(content)
    
    filesize = len(content)
    
    # 计算 full_path
    conn = get_file_db()
    try:
        depth = 0
        parent_path = ""
        if parent_id:
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ?",
                (parent_id, current_user.id)
            )
            parent = cursor.fetchone()
            if parent:
                depth = parent['depth'] + 1
                parent_dict = dict(parent); parent_path = parent_dict.get('full_path', '') or ''
        
        full_path = f"{parent_path}/{file.filename}" if parent_path else f"/{file.filename}"
        
        # 使用参数化查询防止SQL注入
        rel_path = f"files/{current_user.id}/{stored_name}"
        
        conn.execute(
            """INSERT INTO files (user_id, parent_id, name, is_folder, path, full_path, depth, size, mime_type)
               VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)""",
            (current_user.id, parent_id, file.filename, rel_path, full_path, depth, filesize, file.content_type or "application/octet-stream")
        )
        conn.commit()
        
        cursor = conn.execute("SELECT last_insert_rowid() as id")
        file_id = cursor.fetchone()['id']
        
        # 清除缓存
        invalidate_cache("files")
        
        return {
            "id": file_id,
            "name": file.filename,
            "size": filesize,
            "mime_type": file.content_type,
            "path": rel_path
        }
    finally:
        conn.close()


# ==================== 分片上传 ====================

@router.post("/files/upload/chunk")
async def upload_chunk(
    file: UploadFile = FastAPIFile(...),
    chunk_index: int = Form(0),
    total_chunks: int = Form(1),
    file_id: Optional[str] = Form(None),
    filename: str = Form(...),
    parent_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """分片上传 - 接收单个分片"""
    # 验证文件名
    result = InputValidator.validate_filename(filename)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.message)
    
    # 验证分片索引
    if chunk_index < 0 or chunk_index >= total_chunks:
        raise HTTPException(status_code=400, detail="Invalid chunk index")
    
    # 如果没有file_id，创建一个
    if not file_id:
        file_id = uuid.uuid4().hex
    
    # 分片目录
    chunk_dir = UPLOAD_DIR / "chunks" / str(current_user.id) / file_id
    chunk_dir.mkdir(exist_ok=True, parents=True)
    
    # 保存分片
    chunk_path = chunk_dir / f"chunk_{chunk_index:04d}"
    content = await file.read()
    
    # 分片大小限制 (50MB)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Chunk too large (max 50MB)")
    
    with open(chunk_path, "wb") as f:
        f.write(content)
    
    # 返回进度
    return {
        "file_id": file_id,
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "received": chunk_index + 1
    }


@router.post("/files/upload/merge")
async def merge_chunks(
    file_id: str = Form(...),
    filename: str = Form(...),
    total_chunks: int = Form(...),
    parent_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """分片上传 - 合并分片"""
    # 验证文件名
    result = InputValidator.validate_filename(filename)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.message)
    
    # 分片目录
    chunk_dir = UPLOAD_DIR / "chunks" / str(current_user.id) / file_id
    
    if not chunk_dir.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    # 验证所有分片存在
    for i in range(total_chunks):
        chunk_path = chunk_dir / f"chunk_{i:04d}"
        if not chunk_path.exists():
            raise HTTPException(status_code=400, detail=f"Missing chunk {i}")
    
    # 获取文件扩展名
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[1].lower()
    
    # 生成存储名
    uuid_part = uuid.uuid4().hex[:8]
    stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid_part}.{ext}" if ext else f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid_part}"
    
    # 合并文件
    user_dir = UPLOAD_DIR / "files" / str(current_user.id)
    user_dir.mkdir(exist_ok=True, parents=True)
    
    final_path = user_dir / stored_name
    
    with open(final_path, "wb") as outfile:
        for i in range(total_chunks):
            chunk_path = chunk_dir / f"chunk_{i:04d}"
            with open(chunk_path, "rb") as infile:
                outfile.write(infile.read())
    
    # 获取文件大小
    filesize = final_path.stat().st_size
    
    # 清理分片
    import shutil
    shutil.rmtree(chunk_dir)
    
    # 计算 full_path
    conn = get_file_db()
    try:
        depth = 0
        parent_path = ""
        if parent_id:
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ?",
                (parent_id, current_user.id)
            )
            parent = cursor.fetchone()
            if parent:
                depth = parent['depth'] + 1
                parent_dict = dict(parent); parent_path = parent_dict.get('full_path', '') or ''
        
        full_path = f"{parent_path}/{filename}" if parent_path else f"/{filename}"
        
        rel_path = f"files/{current_user.id}/{stored_name}"
        
        mime_type = f"image/{ext}" if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'} else "application/octet-stream"
        
        conn.execute(
            """INSERT INTO files (user_id, parent_id, name, is_folder, path, full_path, depth, size, mime_type)
               VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)""",
            (current_user.id, parent_id, filename, rel_path, full_path, depth, filesize, mime_type)
        )
        conn.commit()
        
        cursor = conn.execute("SELECT last_insert_rowid() as id")
        file_id_db = cursor.fetchone()['id']
        
        # 清除缓存
        invalidate_cache("files")
        
        return {
            "id": file_id_db,
            "name": filename,
            "size": filesize,
            "mime_type": mime_type,
            "path": rel_path
        }
    finally:
        conn.close()


# ==================== 文件下载/删除/重命名/移动 ====================

@router.get("/files/{file_id}/download")
async def download_file(file_id: int, current_user: User = Depends(get_current_user)):
    """下载文件"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ? AND is_folder = 0 AND status = 1",
            (file_id, current_user.id)
        )
        file = cursor.fetchone()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # 多路径回退机制
        file_path = UPLOAD_DIR / file['path']
        
        # 如果原路径不存在，按文件名/大小智能搜索
        if not file_path.exists() or not file_path.is_file():
            target_size = file['size']
            target_ext = os.path.splitext(file['name'])[1].lower() if '.' in file['name'] else ''
            
            # 遍历用户目录查找匹配的文件
            user_dir = UPLOAD_DIR / "files" / str(file['user_id'])
            found_path = None
            if user_dir.exists():
                for f in user_dir.iterdir():
                    if f.is_file():
                        # 方法1: 文件名包含原始名称 (前15字符)
                        base_name = os.path.splitext(file['name'])[0][:15].lower()
                        if base_name and base_name in f.stem.lower():
                            found_path = f
                            break
                        
                        # 方法2: 扩展名相同且大小相近 (10%误差)
                        if target_size > 0 and f.suffix.lower() == target_ext:
                            size_diff = abs(f.stat().st_size - target_size)
                            if size_diff < max(target_size * 0.1, 1000):  # 10%或1KB
                                found_path = f
                                break
            
            if found_path:
                file_path = found_path
        
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        return FileResponse(
            path=str(file_path),
            filename=file['name'],
            media_type=file['mime_type'] or "application/octet-stream"
        )
    finally:
        conn.close()


@router.delete("/files/{file_id}")
async def delete_file(file_id: int, current_user: User = Depends(get_current_user)):
    """删除文件（移至回收站）"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ? AND status = 1",
            (file_id, current_user.id)
        )
        file = cursor.fetchone()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # 添加到回收站
        conn.execute(
            """INSERT INTO trash (user_id, file_type, original_id, original_name, stored_path, size, mime_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (current_user.id, "folder" if file['is_folder'] else "file",
             file_id, file['name'], file['path'], file['size'], file['mime_type'])
        )
        
        # 软删除
        conn.execute("UPDATE files SET status = 0 WHERE id = ?", (file_id,))
        conn.commit()
        
        # 清除缓存
        invalidate_cache("files")
        
        return {"message": "File moved to trash"}
    finally:
        conn.close()


@router.put("/files/{file_id}/rename")
async def rename_file(file_id: int, request: FileRename, current_user: User = Depends(get_current_user)):
    """重命名文件"""
    # 验证文件名
    result = InputValidator.validate_filename(request.name)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.message)
    
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ? AND status = 1",
            (file_id, current_user.id)
        )
        file = cursor.fetchone()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        conn.execute("UPDATE files SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                    (request.name, file_id))
        conn.commit()
        
        # 清除缓存
        invalidate_cache("files")
        
        return {"message": "File renamed", "name": request.name}
    finally:
        conn.close()


@router.get("/folders")
async def list_folders(current_user: User = Depends(get_current_user)):
    """获取文件夹列表（用于移动文件）"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT id, parent_id, name, path, full_path, depth FROM files WHERE user_id = ? AND is_folder = 1 AND status = 1 ORDER BY full_path",
            (current_user.id,)
        )
        folders = [dict(row) for row in cursor.fetchall()]
        return folders
    finally:
        conn.close()


@router.put("/files/{file_id}/move")
async def move_file(file_id: int, request: FileMove, current_user: User = Depends(get_current_user)):
    """移动文件"""
    conn = get_file_db()
    try:
        # 检查文件是否存在
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ? AND status = 1",
            (file_id, current_user.id)
        )
        file = cursor.fetchone()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # 检查目标文件夹是否存在
        if request.parent_id:
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ? AND is_folder = 1 AND status = 1",
                (request.parent_id, current_user.id)
            )
            target_folder = cursor.fetchone()
            if not target_folder:
                raise HTTPException(status_code=404, detail="Target folder not found")
            
            # 不能移动到自己的子文件夹
            if request.parent_id == file_id:
                raise HTTPException(status_code=400, detail="Cannot move file to itself")
            
            new_parent_id = request.parent_id
            new_path = target_folder['full_path']
            new_full_path = f"{target_folder['full_path']}/{file['name']}"
            new_depth = target_folder['depth'] + 1
        else:
            # 移动到根目录
            new_parent_id = None
            new_path = "/"
            new_full_path = f"/{file['name']}"
            new_depth = 0
        
        # 更新文件路径
        conn.execute(
            "UPDATE files SET parent_id = ?, path = ?, full_path = ?, depth = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_parent_id, new_path, new_full_path, new_depth, file_id)
        )
        conn.commit()
        
        return {"message": "File moved successfully", "new_path": new_full_path, "file_name": file['name'], "parent_id": new_parent_id}
    finally:
        conn.close()


# ==================== 文件搜索 ====================

@router.get("/search")
async def search_files(
    q: str,
    type_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    current_user: User = Depends(get_current_user)
):
    """搜索文件"""
    # 验证搜索词 - 防止SQL注入
    result = InputValidator.validate_search_query(q)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.message)
    
    # 限制分页
    if per_page > 100:
        per_page = 100
    if page < 1:
        page = 1
    
    # 使用参数化查询防止SQL注入
    conn = get_file_db()
    try:
        offset = (page - 1) * per_page
        
        # 安全转义搜索词
        search_term = f"%{SQLSanitizer.escape_like(q)}%"
        
        query = "SELECT * FROM files WHERE user_id = ? AND status = 1 AND (name LIKE ? ESCAPE '\\' OR full_path LIKE ? ESCAPE '\\')"
        params = [current_user.id, search_term, search_term]
        
        if type_filter == "folder":
            query += " AND is_folder = 1"
        elif type_filter == "image":
            query += " AND is_folder = 0 AND mime_type LIKE 'image/%'"
        
        query += " ORDER BY is_folder DESC, name LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        cursor = conn.execute(query, params)
        files = [dict(row) for row in cursor.fetchall()]
        
        # Sanitize output
        for f in files:
            f['name'] = InputValidator.sanitize_string(f.get('name', ''))
        
        # 总数 - 使用相同的安全转义
        total_cursor = conn.execute(
            "SELECT COUNT(*) as count FROM files WHERE user_id = ? AND status = 1 AND name LIKE ? ESCAPE '\\'",
            (current_user.id, search_term)
        )
        total = total_cursor.fetchone()['count']
        
        return {"files": files, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


# ==================== 回收站 ====================

@router.get("/trash")
async def get_trash(current_user: User = Depends(get_current_user)):
    """获取回收站文件列表"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM trash WHERE user_id = ? ORDER BY deleted_at DESC",
            (current_user.id,)
        )
        items = [dict(row) for row in cursor.fetchall()]
        return items
    finally:
        conn.close()


@router.post("/trash/restore/{trash_id}")
async def restore_trash(trash_id: int, current_user: User = Depends(get_current_user)):
    """还原文件"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM trash WHERE id = ? AND user_id = ?",
            (trash_id, current_user.id)
        )
        trash_item = cursor.fetchone()
        if not trash_item:
            raise HTTPException(status_code=404, detail="Trash item not found")
        
        # 恢复文件状态
        conn.execute("UPDATE files SET status = 1 WHERE id = ?", (trash_item['original_id'],))
        
        # 删除回收站记录
        conn.execute("DELETE FROM trash WHERE id = ?", (trash_id,))
        conn.commit()
        
        return {"message": "File restored"}
    finally:
        conn.close()


@router.post("/trash/empty")
async def empty_trash(current_user: User = Depends(get_current_user)):
    """清空回收站"""
    conn = get_file_db()
    try:
        # 获取所有回收站项目
        cursor = conn.execute(
            "SELECT original_id FROM trash WHERE user_id = ?",
            (current_user.id,)
        )
        items = cursor.fetchall()
        
        # 删除所有文件记录
        for item in items:
            conn.execute("DELETE FROM files WHERE id = ?", (item['original_id'],))
        
        # 清空回收站记录
        conn.execute("DELETE FROM trash WHERE user_id = ?", (current_user.id,))
        conn.commit()
        
        return {"message": "Trash emptied", "count": len(items)}
    finally:
        conn.close()


@router.delete("/trash/{trash_id}")
async def permanent_delete_trash(trash_id: int, current_user: User = Depends(get_current_user)):
    """永久删除"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM trash WHERE id = ? AND user_id = ?",
            (trash_id, current_user.id)
        )
        trash_item = cursor.fetchone()
        if not trash_item:
            raise HTTPException(status_code=404, detail="Trash item not found")
        
        # 删除文件记录
        conn.execute("DELETE FROM files WHERE id = ?", (trash_item['original_id'],))
        
        # 删除回收站记录
        conn.execute("DELETE FROM trash WHERE id = ?", (trash_id,))
        conn.commit()
        
        return {"message": "File permanently deleted"}
    finally:
        conn.close()


# ==================== 批量操作（Job 支持）====================

class BatchDeleteRequest(BaseModel):
    file_ids: List[int]


class BatchMoveRequest(BaseModel):
    file_ids: List[int]
    target_parent_id: int


@router.post("/files/batch-delete")
async def batch_delete_files(
    request: BatchDeleteRequest,
    current_user: User = Depends(get_current_user)
):
    """
    批量删除文件（使用 Job）
    返回任务 ID，可以通过 /api/v1/jobs/{job_id} 查询状态
    """
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="No files specified")
    
    # 创建任务
    job = job_service.create_job(
        description=f"Batch delete {len(request.file_ids)} files"
    )
    job_id = job.id
    
    # 异步执行
    def _batch_delete():
        conn = get_file_db()
        try:
            job_service.set_running(job_id)
            total = len(request.file_ids)
            deleted_count = 0
            
            for i, file_id in enumerate(request.file_ids):
                cursor = conn.execute(
                    "SELECT * FROM files WHERE id = ? AND user_id = ?",
                    (file_id, current_user.id)
                )
                file = cursor.fetchone()
                
                if file:
                    # 移动到回收站
                    conn.execute("""
                        INSERT INTO trash (user_id, file_type, original_id, original_name, stored_path, size, mime_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        current_user.id,
                        'folder' if file['is_folder'] else 'file',
                        file['id'],
                        file['name'],
                        file['full_path'],
                        file['size'],
                        file['mime_type']
                    ))
                    conn.execute("UPDATE files SET status = 0 WHERE id = ?", (file_id,))
                    deleted_count += 1
                
                # 更新进度
                progress = int((i + 1) / total * 100)
                job_service.update_progress(job_id, progress, JobState.RUNNING)
            
            conn.commit()
            job_service.complete(job_id, {"deleted": deleted_count, "total": total})
        except Exception as e:
            job_service.fail(job_id, str(e))
        finally:
            conn.close()
    
    # 启动异步任务
    import threading
    thread = threading.Thread(target=_batch_delete)
    thread.daemon = True
    thread.start()
    
    return {
        "job_id": job_id,
        "message": "Batch delete task started",
        "total_files": len(request.file_ids)
    }


@router.post("/files/batch-move")
async def batch_move_files(
    request: BatchMoveRequest,
    current_user: User = Depends(get_current_user)
):
    """
    批量移动文件（使用 Job）
    返回任务 ID，可以通过 /api/v1/jobs/{job_id} 查询状态
    """
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="No files specified")
    
    # 验证目标文件夹存在
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ? AND is_folder = 1",
            (request.target_parent_id, current_user.id)
        )
        target_folder = cursor.fetchone()
        
        if not target_folder:
            raise HTTPException(status_code=404, detail="Target folder not found")
    finally:
        conn.close()
    
    # 创建任务
    job = job_service.create_job(
        description=f"Batch move {len(request.file_ids)} files to folder {request.target_parent_id}"
    )
    job_id = job.id
    
    # 异步执行
    def _batch_move():
        conn = get_file_db()
        try:
            job_service.set_running(job_id)
            total = len(request.file_ids)
            moved_count = 0
            
            for i, file_id in enumerate(request.file_ids):
                cursor = conn.execute(
                    "SELECT * FROM files WHERE id = ? AND user_id = ?",
                    (file_id, current_user.id)
                )
                file = cursor.fetchone()
                
                if file:
                    old_path = file['full_path']
                    old_name = file['name']
                    
                    # 构建新路径
                    new_path = f"{target_folder['full_path']}/{old_name}"
                    new_depth = target_folder['depth'] + 1
                    
                    conn.execute("""
                        UPDATE files 
                        SET parent_id = ?, path = ?, full_path = ?, depth = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (request.target_parent_id, target_folder['path'], new_path, new_depth, file_id))
                    moved_count += 1
                
                # 更新进度
                progress = int((i + 1) / total * 100)
                job_service.update_progress(job_id, progress, JobState.RUNNING)
            
            conn.commit()
            invalidate_cache(f"files:{current_user.id}")
            job_service.complete(job_id, {"moved": moved_count, "total": total})
        except Exception as e:
            job_service.fail(job_id, str(e))
        finally:
            conn.close()
    
    # 启动异步任务
    import threading
    thread = threading.Thread(target=_batch_move)
    thread.daemon = True
    thread.start()
    
    return {
        "job_id": job_id,
        "message": "Batch move task started",
        "total_files": len(request.file_ids),
        "target_folder_id": request.target_parent_id
    }