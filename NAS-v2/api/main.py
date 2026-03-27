"""
NAS API 主程序 (整合版)
基于 TrueNAS 架构的私有 NAS - 包含完整文件管理功能

性能优化与安全加固版本
- 数据库索引优化
- API响应缓存
- 大文件分片上传
- 输入验证增强
- SQL注入防护
- XSS防护
- 密码强度验证
- 全局异常捕获
- 错误日志记录
"""
import os
import sys
import uuid
import secrets
import re
import time
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from dataclasses import asdict

# 添加项目根目录到路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Depends, HTTPException, status, Header, UploadFile, File as FastAPIFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator, constr, model_validator
import jwt

from core.config import config
from core.security import InputValidator, ValidationResult, PasswordStrengthChecker, SQLSanitizer
from core.cache import api_cache, cached, invalidate_cache, get_cache_stats
from core.logging import (
    logger, ErrorLogger, NASException, ValidationError, 
    AuthenticationError, AuthorizationError, NotFoundError
)
from storage.zfs import zfs_manager, ZFSPool, ZFSDataset
from share.smb import smb_manager, SMBShare
from share.nfs import nfs_manager, NFSShare
from share.snapshot import snapshot_manager, ZFSSnapshot
from security.auth import auth_manager, User

# ==================== 上传配置 ====================
UPLOAD_DIR = Path("/home/test/.openclaw/workspace/NAS-v2/uploads")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
for subdir in ['files', 'photos', 'thumbs']:
    (UPLOAD_DIR / subdir).mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'pdf', 'doc', 'docx', 'zip', 'rar', 'txt', 'mp3', 'wav'}

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
    
    # 相册表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_encrypted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_albums_user_id ON albums(user_id)")
    
    # 照片表 - 带索引优化
    conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            album_id INTEGER,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            path TEXT,
            thumbnail_path TEXT,
            size INTEGER DEFAULT 0,
            mime_type TEXT,
            width INTEGER,
            height INTEGER,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_album_id ON photos(album_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_uploaded ON photos(uploaded_at)")
    
    # 分享表 - 带索引优化
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            file_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            expire_hours INTEGER DEFAULT 24,
            view_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shares_user_id ON shares(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shares_token ON shares(token)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shares_file ON shares(file_type, file_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_shares_expires ON shares(expires_at)")
    
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
    logger.info("数据库初始化完成，已添加索引优化")
    return db_path

FILE_DB_PATH = init_file_db()

def get_file_db():
    """获取文件数据库连接"""
    import sqlite3
    conn = sqlite3.connect(str(FILE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# 创建 FastAPI 应用
app = FastAPI(
    title="NAS API",
    description="TrueNAS-style Private NAS System - 完整版",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 全局异常处理 ====================

@app.exception_handler(NASException)
async def nas_exception_handler(request: Request, exc: NASException):
    """自定义NAS异常处理"""
    logger.warning(f"[{exc.code}] {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理"""
    errors = exc.errors()
    error_messages = []
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        error_messages.append(f"{field}: {error.get('msg', 'Invalid')}")
    
    logger.warning(f"Validation error: {error_messages}")
    return JSONResponse(
        status_code=400,
        content={
            "error": "VALIDATION_ERROR",
            "message": "请求参数验证失败",
            "details": error_messages
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    error_id = ErrorLogger.log_error(
        error=exc,
        request_info={
            "method": request.method,
            "path": str(request.url),
            "client": request.client.host if request.client else None
        }
    )
    logger.error(f"Unhandled exception [{error_id}]: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试",
            "error_id": error_id
        }
    )


# ==================== 中间件 - 请求日志 ====================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求"""
    start_time = time.time()
    client_ip = request.client.host if request.client else None
    
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        # 记录访问日志
        ErrorLogger.log_access(
            method=request.method,
            path=str(request.url),
            status_code=response.status_code,
            duration_ms=duration_ms,
            ip=client_ip
        )
        
        # 慢请求警告
        if duration_ms > 3000:
            logger.warning(f"Slow request: {request.method} {request.url} took {duration_ms:.0f}ms")
        
        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Request failed: {request.method} {request.url} - {str(e)}")
        raise


# ==================== 请求模型（带验证） ====================

class LoginRequest(BaseModel):
    email: str
    password: str
    
    @field_validator('email')
    def validate_email(cls, v):
        result = InputValidator.validate_email(v)
        if not result.valid:
            raise ValueError(result.message)
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict


class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    email: str
    password: str
    role: str = "user"
    
    @field_validator('email')
    def validate_email(cls, v):
        result = InputValidator.validate_email(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('password')
    def validate_password(cls, v):
        result = InputValidator.validate_password_strength(v)
        if not result.valid:
            raise ValueError(result.message)
        return v
    
    @field_validator('role')
    def validate_role(cls, v):
        allowed = ['user', 'admin', 'guest']
        if v not in allowed:
            raise ValueError(f"Invalid role. Allowed: {allowed}")
        return v


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
    
    @field_validator('new_password')
    def validate_new_password(cls, v):
        result = InputValidator.validate_password_strength(v)
        if not result.valid:
            raise ValueError(result.message)
        return v


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


class AlbumCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = None
    is_encrypted: bool = False


class ShareCreate(BaseModel):
    file_type: str  # file, photo, or folder
    file_id: int
    password: Optional[str] = None
    expire_hours: int = 24
    
    @field_validator('file_type')
    def validate_file_type(cls, v):
        if v not in ['file', 'photo', 'folder']:
            raise ValueError("file_type must be 'file', 'photo', or 'folder'")
        return v
    
    @field_validator('expire_hours')
    def validate_expire_hours(cls, v):
        if v < 1 or v > 8760:  # 1小时到1年
            raise ValueError("expire_hours must be between 1 and 8760")
        return v


class ShareLinkCreate(BaseModel):
    """前端分享链接创建请求模型"""
    file_ids: List[int]
    expires_days: int = 1
    password: Optional[str] = None
    
    @field_validator('file_ids')
    def validate_file_ids(cls, v):
        if not v:
            raise ValueError("file_ids cannot be empty")
        if len(v) > 50:
            raise ValueError("Maximum 50 files can be shared at once")
        return v


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


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return current_user


# ==================== 认证接口 ====================

@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录"""
    user = auth_manager.authenticate(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    token = auth_manager.create_token(user)
    
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    )


@app.post("/api/v1/auth/register")
async def register(user_data: UserCreate):
    """用户注册"""
    result = auth_manager.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role
    )
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.post("/api/v1/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """用户登出"""
    return {"status": "success", "message": "Logged out"}


@app.get("/api/v1/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }


# ==================== 用户管理 ====================

@app.get("/api/v1/users")
async def list_users(current_user: User = Depends(require_admin)):
    """列出所有用户"""
    users = auth_manager.list_users()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at,
            "last_login": u.last_login,
            "enabled": u.enabled
        }
        for u in users
    ]


@app.post("/api/v1/users")
async def create_user(user_data: UserCreate, current_user: User = Depends(require_admin)):
    """创建用户"""
    result = auth_manager.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role
    )
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.delete("/api/v1/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(require_admin)):
    """删除用户"""
    result = auth_manager.delete_user(user_id)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.put("/api/v1/users/me/password")
async def change_password(password_data: PasswordChange, current_user: User = Depends(get_current_user)):
    """修改密码"""
    result = auth_manager.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password
    )
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


# ==================== 文件管理 ====================

@app.get("/api/v1/files")
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


@app.get("/api/v1/files/{file_id}")
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


@app.post("/api/v1/files/folder")
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


@app.post("/api/v1/files/upload")
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

@app.post("/api/v1/files/upload/chunk")
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


@app.post("/api/v1/files/upload/merge")
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


@app.get("/api/v1/files/{file_id}/download")
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
        
        file_path = UPLOAD_DIR / file['path']
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        return FileResponse(
            path=str(file_path),
            filename=file['name'],
            media_type=file['mime_type'] or "application/octet-stream"
        )
    finally:
        conn.close()


@app.delete("/api/v1/files/{file_id}")
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


@app.put("/api/v1/files/{file_id}/rename")
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


@app.get("/api/v1/files/folders")
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


class FileMove(BaseModel):
    parent_id: Optional[int] = None


@app.put("/api/v1/files/{file_id}/move")
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
        
        return {"message": "File moved successfully", "parent_id": new_parent_id}
    finally:
        conn.close()


# ==================== 文件搜索 ====================

@app.get("/api/v1/search")
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

@app.get("/api/v1/trash")
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


@app.post("/api/v1/trash/restore/{trash_id}")
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


@app.post("/api/v1/trash/empty")
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


@app.delete("/api/v1/trash/{trash_id}")
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


# ==================== 相册管理 ====================

@app.get("/api/v1/albums")
@cached(ttl=30, key_prefix="albums")
async def get_albums(current_user: User = Depends(get_current_user)):
    """获取相册列表"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM albums WHERE user_id = ? ORDER BY created_at DESC",
            (current_user.id,)
        )
        albums = []
        for row in cursor.fetchall():
            album = dict(row)
            # 获取照片数量
            count_cursor = conn.execute(
                "SELECT COUNT(*) as count FROM photos WHERE album_id = ?",
                (album['id'],)
            )
            album['photo_count'] = count_cursor.fetchone()['count']
            albums.append(album)
        return albums
    finally:
        conn.close()


@app.post("/api/v1/albums")
async def create_album(album: AlbumCreate, current_user: User = Depends(get_current_user)):
    """创建相册"""
    conn = get_file_db()
    try:
        conn.execute(
            "INSERT INTO albums (user_id, name, description, is_encrypted) VALUES (?, ?, ?, ?)",
            (current_user.id, album.name, album.description, 1 if album.is_encrypted else 0)
        )
        conn.commit()
        
        cursor = conn.execute("SELECT last_insert_rowid() as id")
        album_id = cursor.fetchone()['id']
        
        # 清除缓存
        invalidate_cache("albums")
        
        return {"id": album_id, "name": album.name, "message": "Album created"}
    finally:
        conn.close()


@app.get("/api/v1/albums/{album_id}")
async def get_album(album_id: int, current_user: User = Depends(get_current_user)):
    """获取相册详情"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM albums WHERE id = ? AND user_id = ?",
            (album_id, current_user.id)
        )
        album = cursor.fetchone()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
        
        album = dict(album)
        
        # 获取相册中的照片
        cursor = conn.execute(
            "SELECT * FROM photos WHERE album_id = ? ORDER BY uploaded_at DESC",
            (album_id,)
        )
        album['photos'] = [dict(row) for row in cursor.fetchall()]
        
        return album
    finally:
        conn.close()


@app.delete("/api/v1/albums/{album_id}")
async def delete_album(album_id: int, current_user: User = Depends(get_current_user)):
    """删除相册"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM albums WHERE id = ? AND user_id = ?",
            (album_id, current_user.id)
        )
        album = cursor.fetchone()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
        
        # 删除相册中的照片文件
        cursor = conn.execute("SELECT * FROM photos WHERE album_id = ?", (album_id,))
        for photo in cursor.fetchall():
            if photo['path']:
                file_path = UPLOAD_DIR / photo['path']
                if file_path.exists():
                    file_path.unlink()
        
        # 删除照片记录
        conn.execute("DELETE FROM photos WHERE album_id = ?", (album_id,))
        
        # 删除相册
        conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        conn.commit()
        
        return {"message": "Album deleted"}
    finally:
        conn.close()


# ==================== 照片管理 ====================

@app.get("/api/v1/photos")
async def get_photos(
    album_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 50,
    current_user: User = Depends(get_current_user)
):
    """获取照片列表"""
    conn = get_file_db()
    try:
        offset = (page - 1) * per_page
        
        if album_id:
            cursor = conn.execute(
                "SELECT * FROM photos WHERE user_id = ? AND album_id = ? ORDER BY uploaded_at DESC LIMIT ? OFFSET ?",
                (current_user.id, album_id, per_page, offset)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM photos WHERE user_id = ? ORDER BY uploaded_at DESC LIMIT ? OFFSET ?",
                (current_user.id, per_page, offset)
            )
        
        photos = [dict(row) for row in cursor.fetchall()]
        return photos
    finally:
        conn.close()


@app.post("/api/v1/photos/upload")
async def upload_photo(
    file: UploadFile = FastAPIFile(...),
    album_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """上传照片"""
    # 验证文件类型
    allowed_photo_ext = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}
    file_ext = ""
    if "." in file.filename:
        file_ext = file.filename.rsplit(".", 1)[1].lower()
    
    if file_ext not in allowed_photo_ext:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    
    # 如果指定了album_id，验证相册归属
    if album_id:
        conn = get_file_db()
        try:
            cursor = conn.execute(
                "SELECT id FROM albums WHERE id = ? AND user_id = ?",
                (album_id, current_user.id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Album not found")
        finally:
            conn.close()
    
    # 保存文件
    stored_name = f"{uuid.uuid4().hex}.{file_ext}"
    photo_dir = UPLOAD_DIR / "photos" / str(current_user.id)
    photo_dir.mkdir(exist_ok=True, parents=True)
    
    file_path = photo_dir / stored_name
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 获取图片尺寸
    width, height = None, None
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            width, height = img.size
    except:
        pass
    
    # 创建照片记录
    conn = get_file_db()
    try:
        rel_path = f"photos/{current_user.id}/{stored_name}"
        
        conn.execute(
            """INSERT INTO photos (user_id, album_id, original_name, stored_name, path, size, mime_type, width, height)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (current_user.id, album_id, file.filename, stored_name, rel_path, 
             len(content), file.content_type or f"image/{file_ext}", width, height)
        )
        conn.commit()
        
        cursor = conn.execute("SELECT last_insert_rowid() as id")
        photo_id = cursor.fetchone()['id']
        
        return {
            "id": photo_id,
            "original_name": file.filename,
            "path": rel_path,
            "size": len(content),
            "mime_type": file.content_type
        }
    finally:
        conn.close()


@app.get("/api/v1/photos/{photo_id}")
async def get_photo(photo_id: int, current_user: User = Depends(get_current_user)):
    """获取照片"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM photos WHERE id = ? AND user_id = ?",
            (photo_id, current_user.id)
        )
        photo = cursor.fetchone()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        photo = dict(photo)
        # 返回照片文件
        if photo['path']:
            file_path = UPLOAD_DIR / photo['path']
            if file_path.exists():
                return FileResponse(
                    path=str(file_path),
                    filename=photo['original_name'],
                    media_type=photo['mime_type']
                )
        raise HTTPException(status_code=404, detail="Photo file not found")
    finally:
        conn.close()


@app.get("/api/v1/photos/{photo_id}/thumbnail")
async def get_photo_thumbnail(photo_id: int, current_user: User = Depends(get_current_user)):
    """获取照片缩略图"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM photos WHERE id = ? AND user_id = ?",
            (photo_id, current_user.id)
        )
        photo = cursor.fetchone()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        photo = dict(photo)
        # 返回照片文件（缩略图功能可后续优化）
        if photo['path']:
            file_path = UPLOAD_DIR / photo['path']
            if file_path.exists():
                return FileResponse(
                    path=str(file_path),
                    filename=photo['original_name'],
                    media_type=photo['mime_type']
                )
        raise HTTPException(status_code=404, detail="Photo file not found")
    finally:
        conn.close()


@app.delete("/api/v1/photos/{photo_id}")
async def delete_photo(photo_id: int, current_user: User = Depends(get_current_user)):
    """删除照片"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM photos WHERE id = ? AND user_id = ?",
            (photo_id, current_user.id)
        )
        photo = cursor.fetchone()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        # 删除文件
        if photo['path']:
            file_path = UPLOAD_DIR / photo['path']
            if file_path.exists():
                file_path.unlink()
        
        conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        conn.commit()
        
        return {"message": "Photo deleted"}
    finally:
        conn.close()


# ==================== 分享功能 ====================

@app.post("/api/v1/shares")
async def create_share(share: ShareCreate, current_user: User = Depends(get_current_user)):
    """创建分享链接"""
    conn = get_file_db()
    try:
        # 验证文件属于当前用户
        if share.file_type == "file":
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ? AND is_folder = 0",
                (share.file_id, current_user.id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="File not found")
        elif share.file_type == "folder":
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ? AND is_folder = 1",
                (share.file_id, current_user.id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Folder not found")
        else:
            cursor = conn.execute(
                "SELECT * FROM photos WHERE id = ? AND user_id = ?",
                (share.file_id, current_user.id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Photo not found")
        
        # 生成 token
        share_token = secrets.token_urlsafe(32)
        password_hash = None
        
        if share.password:
            from passlib.hash import bcrypt
            password_hash = bcrypt.hash(share.password)
        
        expires_at = datetime.now() + timedelta(hours=share.expire_hours)
        
        conn.execute(
            """INSERT INTO shares (user_id, file_type, file_id, token, password_hash, expire_hours, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (current_user.id, share.file_type, share.file_id, share_token, 
             password_hash, share.expire_hours, expires_at.isoformat())
        )
        conn.commit()
        
        return {
            "id": conn.execute("SELECT last_insert_rowid()").fetchone()[0],
            "token": share_token,
            "share_url": f"/share/{share_token}",
            "expires_at": expires_at.isoformat()
        }
    finally:
        conn.close()


@app.get("/api/v1/shares")
async def get_my_shares(current_user: User = Depends(get_current_user)):
    """获取我的分享"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM shares WHERE user_id = ? ORDER BY created_at DESC",
            (current_user.id,)
        )
        
        shares = []
        for row in cursor.fetchall():
            share = dict(row)
            
            # 获取文件名
            if share['file_type'] == "file":
                file_cursor = conn.execute("SELECT name FROM files WHERE id = ?", (share['file_id'],))
                file_row = file_cursor.fetchone()
                share['file_name'] = file_row['name'] if file_row else None
            else:
                photo_cursor = conn.execute("SELECT original_name FROM photos WHERE id = ?", (share['file_id'],))
                photo_row = photo_cursor.fetchone()
                share['file_name'] = photo_row['original_name'] if photo_row else None
            
            shares.append(share)
        
        return shares
    finally:
        conn.close()


@app.get("/share/{token}")
async def view_share(token: str, password: Optional[str] = None):
    """访问分享链接"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM shares WHERE token = ? AND is_active = 1",
            (token,)
        )
        share = cursor.fetchone()
        
        if not share:
            raise HTTPException(status_code=404, detail="Share not found")
        
        if share['expires_at']:
            expires_at = datetime.fromisoformat(share['expires_at'])
            if expires_at < datetime.now():
                raise HTTPException(status_code=410, detail="Share expired")
        
        # 检查密码
        if share['password_hash']:
            from passlib.hash import bcrypt
            if not password or not bcrypt.verify(password, share['password_hash']):
                return {"require_password": True, "token": token}
        
        # 增加访问计数
        conn.execute("UPDATE shares SET view_count = view_count + 1 WHERE id = ?", (share['id'],))
        conn.commit()
        
        # 返回文件
        if share['file_type'] == "file":
            cursor = conn.execute("SELECT * FROM files WHERE id = ?", (share['file_id'],))
            file = cursor.fetchone()
            if file:
                # 检查文件是否存在
                file_path = UPLOAD_DIR / file['path']
                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="File not found on disk")
                return FileResponse(
                    path=str(file_path),
                    filename=file['name'],
                    media_type=file['mime_type']
                )
        elif share['file_type'] == "folder":
            # 返回文件夹内容列表
            cursor = conn.execute("SELECT * FROM files WHERE id = ?", (share['file_id'],))
            folder = cursor.fetchone()
            if folder:
                folder_path = UPLOAD_DIR / folder['path']
                if not folder_path.exists():
                    raise HTTPException(status_code=404, detail="Folder not found on disk")
                
                # 获取文件夹内的文件和子文件夹
                items = []
                for item in folder_path.iterdir():
                    items.append({
                        "name": item.name,
                        "is_folder": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                        "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                    })
                
                return {
                    "folder_name": folder['name'],
                    "items": items
                }
        else:
            cursor = conn.execute("SELECT * FROM photos WHERE id = ?", (share['file_id'],))
            photo = cursor.fetchone()
            if photo:
                photo_path = UPLOAD_DIR / photo['path']
                if not photo_path.exists():
                    raise HTTPException(status_code=404, detail="Photo not found on disk")
                return FileResponse(
                    path=str(photo_path),
                    filename=photo['original_name'],
                    media_type=photo['mime_type']
                )
        
        raise HTTPException(status_code=404, detail="File not found")
    finally:
        conn.close()


# ==================== 分享链接API (前端调用) ====================

@app.get("/api/v1/shares/links")
async def get_share_links(current_user: User = Depends(get_current_user)):
    """获取分享链接列表 (前端API)"""
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM shares WHERE user_id = ? ORDER BY created_at DESC",
            (current_user.id,)
        )
        
        shares = []
        for row in cursor.fetchall():
            share = dict(row)
            
            # 获取文件名
            if share['file_type'] == 'folder':
                file_cursor = conn.execute("SELECT name FROM files WHERE id = ? AND is_folder = 1", (share['file_id'],))
                file_row = file_cursor.fetchone()
                share['file_name'] = file_row['name'] if file_row else None
            elif share['file_type'] == 'file':
                file_cursor = conn.execute("SELECT name FROM files WHERE id = ? AND is_folder = 0", (share['file_id'],))
                file_row = file_cursor.fetchone()
                share['file_name'] = file_row['name'] if file_row else None
            else:
                photo_cursor = conn.execute("SELECT original_name FROM photos WHERE id = ?", (share['file_id'],))
                photo_row = photo_cursor.fetchone()
                share['file_name'] = photo_row['original_name'] if photo_row else None
            
            shares.append(share)
        
        return shares
    finally:
        conn.close()


@app.post("/api/v1/shares/links")
async def create_share_link(request: ShareLinkCreate, current_user: User = Depends(get_current_user)):
    """创建分享链接 (前端API)"""
    conn = get_file_db()
    try:
        if not request.file_ids:
            raise HTTPException(status_code=400, detail="No files selected")
        
        results = []
        for file_id in request.file_ids:
            # 判断是文件、文件夹还是照片
            file_cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ?",
                (file_id, current_user.id)
            )
            file_row = file_cursor.fetchone()
            
            if file_row:
                file_type = "folder" if file_row['is_folder'] else "file"
            else:
                photo_cursor = conn.execute(
                    "SELECT * FROM photos WHERE id = ? AND user_id = ?",
                    (file_id, current_user.id)
                )
                photo_row = photo_cursor.fetchone()
                if not photo_row:
                    continue
                file_type = "photo"
            
            # 生成 token
            share_token = secrets.token_urlsafe(32)
            password_hash = None
            
            if request.password:
                from passlib.hash import bcrypt
                password_hash = bcrypt.hash(request.password)
            
            expire_hours = request.expires_days * 24 if request.expires_days > 0 else 24
            expires_at = datetime.now() + timedelta(hours=expire_hours)
            
            conn.execute(
                """INSERT INTO shares (user_id, file_type, file_id, token, password_hash, expire_hours, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (current_user.id, file_type, file_id, share_token, 
                 password_hash, expire_hours, expires_at.isoformat())
            )
            conn.commit()
            
            results.append({
                "id": conn.execute("SELECT last_insert_rowid()").fetchone()[0],
                "token": share_token,
                "share_url": f"/share/{share_token}",
                "expires_at": expires_at.isoformat()
            })
        
        return results
    finally:
        conn.close()


@app.delete("/api/v1/shares/{share_id}")
async def delete_share_link(share_id: int, current_user: User = Depends(get_current_user)):
    """删除分享链接"""
    conn = get_file_db()
    try:
        # 验证分享属于当前用户
        cursor = conn.execute(
            "SELECT * FROM shares WHERE id = ? AND user_id = ?",
            (share_id, current_user.id)
        )
        share = cursor.fetchone()
        
        if not share:
            raise HTTPException(status_code=404, detail="Share not found")
        
        # 软删除 - 设置 is_active = 0
        conn.execute("UPDATE shares SET is_active = 0 WHERE id = ?", (share_id,))
        conn.commit()
        
        return {"message": "Share deleted successfully"}
    finally:
        conn.close()


# ==================== 统计数据 ====================

@app.get("/api/v1/stats")
@cached(ttl=60, key_prefix="stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    """获取统计数据"""
    conn = get_file_db()
    try:
        # 相册数
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM albums WHERE user_id = ?",
            (current_user.id,)
        )
        albums = cursor.fetchone()['count']
        
        # 照片数
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM photos WHERE user_id = ?",
            (current_user.id,)
        )
        photos = cursor.fetchone()['count']
        
        # 文件夹数
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM files WHERE user_id = ? AND is_folder = 1 AND status = 1",
            (current_user.id,)
        )
        folders = cursor.fetchone()['count']
        
        # 文件大小
        cursor = conn.execute(
            "SELECT COALESCE(SUM(size), 0) as total FROM files WHERE user_id = ? AND is_folder = 0 AND status = 1",
            (current_user.id,)
        )
        file_size = cursor.fetchone()['total']
        
        # 照片大小
        cursor = conn.execute(
            "SELECT COALESCE(SUM(size), 0) as total FROM photos WHERE user_id = ?",
            (current_user.id,)
        )
        photo_size = cursor.fetchone()['total']
        
        return {
            "albums": albums,
            "photos": photos,
            "folders": folders,
            "files": file_size,
            "photoSize": photo_size,
            "totalSize": file_size + photo_size
        }
    finally:
        conn.close()


# ==================== ZFS 存储管理 (原有功能) ====================

@app.get("/api/v1/storage/pools")
async def list_pools(current_user: User = Depends(get_current_user)):
    """列出所有 ZFS 池"""
    pools = zfs_manager.list_pools()
    return [asdict(p) for p in pools]


@app.post("/api/v1/storage/pools")
async def create_pool(
    name: str,
    vdevs: List[str],
    layout: str = "basic",
    current_user: User = Depends(require_admin)
):
    """创建 ZFS 池"""
    result = zfs_manager.create_pool(name, vdevs, layout)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.get("/api/v1/storage/pools/{pool_name}")
async def get_pool(pool_name: str, current_user: User = Depends(get_current_user)):
    """获取池信息"""
    pool = zfs_manager.get_pool(pool_name)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    
    status_info = zfs_manager.get_pool_status(pool_name)
    disks = zfs_manager.get_disk_info(pool_name)
    
    return {
        "pool": asdict(pool),
        "status": status_info,
        "disks": [asdict(d) for d in disks]
    }


@app.delete("/api/v1/storage/pools/{pool_name}")
async def delete_pool(pool_name: str, force: bool = False, current_user: User = Depends(require_admin)):
    """删除 ZFS 池"""
    result = zfs_manager.destroy_pool(pool_name, force)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.get("/api/v1/storage/datasets")
async def list_datasets(pool: str = None, current_user: User = Depends(get_current_user)):
    """列出数据集"""
    datasets = zfs_manager.list_datasets(pool)
    return [asdict(d) for d in datasets]


@app.post("/api/v1/storage/datasets")
async def create_dataset(
    name: str,
    properties: Dict = None,
    current_user: User = Depends(get_current_user)
):
    """创建数据集"""
    result = zfs_manager.create_dataset(name, properties)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.delete("/api/v1/storage/datasets/{dataset}")
async def delete_dataset(
    dataset: str,
    force: bool = False,
    recursive: bool = False,
    current_user: User = Depends(get_current_user)
):
    """删除数据集"""
    result = zfs_manager.destroy_dataset(dataset, force, recursive)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.post("/api/v1/storage/pools/{pool_name}/scrub")
async def scrub_pool(pool_name: str, current_user: User = Depends(require_admin)):
    """启动池清理"""
    result = zfs_manager.scrub_pool(pool_name)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


# ==================== 共享管理 (原有功能) ====================

@app.get("/api/v1/shares/all")
async def list_all_shares(current_user: User = Depends(get_current_user)):
    """列出所有共享 (SMB/NFS)"""
    smb_shares = smb_manager.list_shares()
    nfs_shares = nfs_manager.list_shares()
    
    return {
        "smb": [asdict(s) for s in smb_shares],
        "nfs": [asdict(s) for s in nfs_shares]
    }


@app.post("/api/v1/shares/smb")
async def create_smb_share(
    name: str,
    path: str,
    comment: str = "",
    writable: bool = True,
    guest_ok: bool = False,
    valid_users: str = "",
    current_user: User = Depends(get_current_user)
):
    """创建 SMB 共享"""
    share = SMBShare(
        name=name,
        path=path,
        comment=comment,
        writable=writable,
        guest_ok=guest_ok,
        valid_users=valid_users
    )
    
    result = smb_manager.create_share(share)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.delete("/api/v1/shares/smb/{name}")
async def delete_smb_share(name: str, current_user: User = Depends(get_current_user)):
    """删除 SMB 共享"""
    result = smb_manager.delete_share(name)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.post("/api/v1/shares/nfs")
async def create_nfs_share(
    path: str,
    clients: str = "*",
    options: str = "rw,sync,no_subtree_check,no_root_squash",
    comment: str = "",
    current_user: User = Depends(get_current_user)
):
    """创建 NFS 共享"""
    share = NFSShare(
        path=path,
        clients=clients,
        options=options,
        comment=comment
    )
    
    result = nfs_manager.create_share(share)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.delete("/api/v1/shares/nfs/{path}")
async def delete_nfs_share(path: str, current_user: User = Depends(get_current_user)):
    """删除 NFS 共享"""
    import urllib.parse
    path = urllib.parse.unquote(path)
    
    result = nfs_manager.delete_share(path)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


# ==================== 快照管理 (原有功能) ====================

@app.get("/api/v1/snapshots")
async def list_snapshots(pool: str = None, dataset: str = None, current_user: User = Depends(get_current_user)):
    """列出快照"""
    snapshots = snapshot_manager.list_snapshots(pool, dataset)
    return [asdict(s) for s in snapshots]


@app.post("/api/v1/snapshots")
async def create_snapshot(
    dataset: str,
    name: str,
    recursive: bool = False,
    current_user: User = Depends(get_current_user)
):
    """创建快照"""
    result = snapshot_manager.create_snapshot(dataset, name, recursive)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.delete("/api/v1/snapshots/{snapshot}")
async def delete_snapshot(snapshot: str, recursive: bool = False, current_user: User = Depends(get_current_user)):
    """删除快照"""
    result = snapshot_manager.delete_snapshot(snapshot, recursive)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@app.post("/api/v1/snapshots/{snapshot}/rollback")
async def rollback_snapshot(snapshot: str, force: bool = False, current_user: User = Depends(get_current_user)):
    """回滚到快照"""
    result = snapshot_manager.rollback_snapshot(snapshot, force)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


# ==================== 系统状态 ====================

@app.get("/api/v1/system/status")
async def get_system_status(current_user: User = Depends(get_current_user)):
    """获取系统状态"""
    pools = zfs_manager.list_pools()
    smb_status = smb_manager.get_status()
    nfs_status = nfs_manager.get_status()
    
    return {
        "pools": len(pools),
        "smb": smb_status,
        "nfs": nfs_status,
        "users": len(auth_manager.list_users())
    }


# ==================== 缓存管理 ====================

@app.get("/api/v1/cache/stats")
async def get_cache_stats_endpoint(current_user: User = Depends(get_current_user)):
    """获取缓存统计"""
    return get_cache_stats()


@app.post("/api/v1/cache/clear")
async def clear_cache(
    pattern: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """清除缓存"""
    count = invalidate_cache(pattern)
    return {"message": f"Cleared {count} cache entries"}


# ==================== 密码强度检查 ====================

@app.get("/api/v1/password/check")
async def check_password_strength(
    password: str,
    current_user: User = Depends(get_current_user)
):
    """检查密码强度"""
    result = PasswordStrengthChecker.check(password)
    return result


# ==================== 前端页面 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """主页"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"ROOT: {ROOT}")
    ui_path = ROOT / "ui" / "index.html"
    logger.info(f"ui_path: {ui_path}, exists: {ui_path.exists()}")
    if ui_path.exists():
        return HTMLResponse(content=ui_path.read_text())
    
    return HTMLResponse(content="""
        <html>
        <head><title>NAS System v2</title></head>
        <body>
            <h1>NAS API v2.0 - Running</h1>
            <p>API Documentation: <a href="/docs">/docs</a></p>
            <p>功能: 文件管理 | ZFS存储 | SMB/NFS共享 | 快照 | 相册 | 分享</p>
        </body>
        </html>
    """)


# ==================== 辅助函数 ====================

def asdict(obj):
    """转换为字典"""
    if hasattr(obj, '__dataclassfields__'):
        result = {}
        for k in obj.__dataclassfields__:
            v = getattr(obj, k)
            if k == 'cap' and v:
                try:
                    result['usage_percent'] = int(v.rstrip('%'))
                except:
                    result['usage_percent'] = 0
            result[k] = v
        return result
    return obj


if __name__ == "__main__":
    import uvicorn
    
    print(f"""
╔════════════════════════════════════════════════════════════╗
║           NAS System v2.0 - 完整版                          ║
║                                                            ║
║  功能: 文件管理 | ZFS存储 | SMB/NFS | 快照 | 相册 | 分享   ║
║                                                            ║
║  API:    http://localhost:{config.port}/api/v1                 ║
║  Docs:   http://localhost:{config.port}/docs                  ║
║                                                            ║
║  Default Admin:                                             ║
║    Username: admin                                          ║
║    Password: admin123                                       ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host=config.host, port=config.port)