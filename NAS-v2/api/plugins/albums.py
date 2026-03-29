"""
相册插件 - 相册和照片管理
"""
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, constr

from security.auth import auth_manager, User
from core.security import InputValidator
from core.cache import cached, invalidate_cache
from core.logging import logger

# ==================== 路径配置 ====================

ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
for subdir in ['files', 'photos', 'thumbs']:
    (UPLOAD_DIR / subdir).mkdir(exist_ok=True)

# ==================== 数据库初始化 ====================

def get_file_db():
    """获取文件数据库连接"""
    import sqlite3
    db_path = ROOT / "data" / "files.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ==================== 路由配置 ====================

router = APIRouter(prefix="/api/v1", tags=["相册"])

# ==================== 请求模型 ====================

class AlbumCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = None
    is_encrypted: bool = False


# ==================== 依赖注入 ====================

def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """获取当前用户 - 从Header获取"""
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


# ==================== 相册管理 ====================

@router.get("/albums")
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


@router.post("/albums")
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


@router.get("/albums/{album_id}")
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


@router.delete("/albums/{album_id}")
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

@router.get("/photos")
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


@router.post("/photos/upload")
async def upload_photo(
    file: UploadFile = FastAPIFile(...),
    album_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """上传照片"""
    import uuid
    
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


@router.get("/photos/{photo_id}")
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


@router.get("/photos/{photo_id}/thumbnail")
async def get_photo_thumbnail(
    photo_id: int, 
    t: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
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


@router.delete("/photos/{photo_id}")
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