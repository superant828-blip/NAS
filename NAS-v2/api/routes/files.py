"""
文件管理路由 - 完整实现
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import aiofiles
import os
import sqlite3
from datetime import datetime

from security.auth import auth_manager, User
from core.logging import logger
from storage.zfs import zfs_manager

router = APIRouter(prefix="/api/v1/files", tags=["文件管理"])

# 上传目录配置
UPLOAD_DIR = Path("/nas-pool/data/uploads")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

# 数据库路径
ROOT = Path(__file__).resolve().parent.parent.parent
FILE_DB = ROOT / "data" / "files.db"


def get_file_db():
    """获取文件数据库连接"""
    conn = sqlite3.connect(str(FILE_DB))
    conn.row_factory = sqlite3.Row
    return conn


class FolderCreateRequest(BaseModel):
    name: str
    parent_id: Optional[int] = None
    path: str = "/"


class RenameRequest(BaseModel):
    name: str


class MoveRequest(BaseModel):
    parent_id: Optional[int] = None
    path: Optional[str] = None


async def get_current_user_id(request: Request) -> int:
    """从Token获取用户ID"""
    auth_header = request.headers.get('authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    
    token = auth_header.replace("Bearer ", "")
    payload = auth_manager.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token无效")
    return payload.get("user_id", 1)


@router.get("/")
async def list_files(
    path: str = Query("/"),
    parent_id: Optional[int] = Query(None),
    sort_by: str = Query("name"),
    order: str = Query("asc"),
    view: str = Query("grid"),
    authorization: str = Query(None)
):
    """获取文件列表"""
    user_id = await get_current_user_id(authorization)
    
    conn = get_file_db()
    try:
        query = "SELECT * FROM files WHERE user_id = ? AND status = 1"
        params = [user_id]
        
        if parent_id:
            query += " AND parent_id = ?"
            params.append(parent_id)
        elif path:
            # 通过path过滤
            pass
        
        # 排序
        sort_column = "name" if sort_by == "name" else "created_at" if sort_by == "date" else "size"
        query += f" ORDER BY is_folder DESC, {sort_column} {'DESC' if order == 'desc' else 'ASC'}"
        
        cursor = conn.execute(query, params)
        files = [dict(row) for row in cursor.fetchall()]
        
        return files
    finally:
        conn.close()


@router.get("/{file_id}")
async def get_file(file_id: int, authorization: str = Query(None)):
    """获取文件详情"""
    user_id = await get_current_user_id(authorization)
    
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ?",
            (file_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="文件不存在")
        return dict(row)
    finally:
        conn.close()


@router.post("/folder")
async def create_folder(
    name: str = Form(...),
    parent_id: Optional[int] = Form(None),
    path: str = Form("/"),
    authorization: str = Query(None)
):
    """创建文件夹"""
    user_id = await get_current_user_id(authorization)
    
    conn = get_file_db()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            """INSERT INTO files 
               (user_id, parent_id, name, is_folder, path, status, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, 1, ?, ?)""",
            (user_id, parent_id, name, f"files/{user_id}/{name}", now, now)
        )
        conn.commit()
        
        return {"id": cursor.lastrowid, "name": name, "is_folder": True}
    except Exception as e:
        logger.error(f"Create folder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    path: str = Form("/"),
    parent_id: Optional[int] = Form(None),
    authorization: str = Query(None)
):
    """上传文件"""
    user_id = await get_current_user_id(authorization)
    
    try:
        # 确保目录存在
        upload_path = UPLOAD_DIR / f"files/{user_id}"
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # 保存文件
        file_path = upload_path / file.filename
        content = await file.read()
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        # 写入数据库
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_file_db()
        try:
            cursor = conn.execute(
                """INSERT INTO files 
                   (user_id, parent_id, name, is_folder, path, size, mime_type, status, created_at, updated_at)
                   VALUES (?, ?, ?, 0, ?, ?, ?, 1, ?, ?)""",
                (user_id, parent_id, file.filename, f"files/{user_id}/{file.filename}", 
                 len(content), file.content_type, now, now)
            )
            conn.commit()
            file_id = cursor.lastrowid
        finally:
            conn.close()
        
        return {
            "success": True,
            "id": file_id,
            "filename": file.filename,
            "size": len(content),
            "path": str(file_path)
        }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    request: Request
):
    """下载文件"""
    user_id = await get_current_user_id(request)
    
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ? AND is_folder = 0",
            (file_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        file_info = dict(row)
        path_val = file_info.get("path", "")
        
        # 多路径搜索：UPLOAD_DIR, ROOT/uploads, 当前目录
        search_dirs = [
            UPLOAD_DIR,
            ROOT / "uploads",
            Path("/nas-pool/data/uploads"),
        ]
        
        file_path = None
        for search_dir in search_dirs:
            # 尝试直接拼接
            test_path = search_dir / path_val
            if test_path.exists():
                file_path = test_path
                break
            # 尝试在files子目录
            test_path = search_dir / "files" / str(user_id) / path_val
            if test_path.exists():
                file_path = test_path
                break
        
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在于磁盘上")
        
        return FileResponse(
            path=file_path,
            filename=file_info["name"],
            media_type=file_info.get("mime_type", "application/octet-stream")
        )
    finally:
        conn.close()


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    authorization: str = Query(None)
):
    """删除文件"""
    user_id = await get_current_user_id(authorization)
    
    conn = get_file_db()
    try:
        # 检查文件是否存在
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ?",
            (file_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 软删除
        conn.execute(
            "UPDATE files SET status = 0, updated_at = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), file_id)
        )
        conn.commit()
        
        return {"success": True, "message": "文件已删除"}
    finally:
        conn.close()


@router.put("/{file_id}/rename")
async def rename_file(
    file_id: int,
    name: str,
    authorization: str = Query(None)
):
    """重命名文件"""
    user_id = await get_current_user_id(authorization)
    
    conn = get_file_db()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE files SET name = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (name, now, file_id, user_id)
        )
        conn.commit()
        
        return {"success": True, "name": name}
    finally:
        conn.close()


@router.put("/{file_id}/move")
async def move_file(
    file_id: int,
    parent_id: Optional[int] = None,
    path: Optional[str] = None,
    authorization: str = Query(None)
):
    """移动文件"""
    user_id = await get_current_user_id(authorization)
    
    conn = get_file_db()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE files SET parent_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (parent_id, now, file_id, user_id)
        )
        conn.commit()
        
        return {"success": True, "parent_id": parent_id}
    finally:
        conn.close()


# 文件搜索
@router.get("/search/all")
async def search_files(
    q: str = Query(..., min_length=1),
    authorization: str = Query(None)
):
    """搜索文件"""
    user_id = await get_current_user_id(authorization)
    
    conn = get_file_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM files WHERE user_id = ? AND status = 1 AND name LIKE ?",
            (user_id, f"%{q}%")
        )
        files = [dict(row) for row in cursor.fetchall()]
        return {"results": files, "total": len(files)}
    finally:
        conn.close()