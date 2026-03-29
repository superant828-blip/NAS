"""
分享插件 - 文件分享、链接分享、SMB/NFS共享
"""
import secrets
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Form, Header
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator

from security.auth import auth_manager, User
from share.smb import smb_manager, SMBShare
from share.nfs import nfs_manager, NFSShare

# ==================== 路径配置 ====================

ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# ==================== 数据库初始化 ====================

def get_file_db():
    """获取文件数据库连接"""
    import sqlite3
    db_path = ROOT / "data" / "files.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ==================== 路由配置 ====================

router = APIRouter(prefix="/api/v1/shares", tags=["分享"])

# ==================== 请求模型 ====================

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


# ==================== 分享功能 ====================

@router.post("")
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


@router.get("")
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


@router.delete("/{share_id}")
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


# ==================== 分享链接API (前端调用) ====================

links_router = APIRouter(prefix="/api/v1/shares/links", tags=["分享链接"])


@links_router.get("")
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


@links_router.post("")
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


# ==================== 访问分享链接 ====================

share_router = APIRouter(tags=["公开分享"])


@share_router.get("/share/{token}")
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
            password_valid = False
            try:
                password_valid = password and bcrypt.verify(password, share['password_hash'])
            except (ValueError, TypeError) as e:
                pass
            if not password_valid:
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


# ==================== SMB/NFS 共享管理 ====================

smb_router = APIRouter(prefix="/api/v1/shares/smb", tags=["SMB共享"])


@smb_router.get("/all")
async def list_all_shares(current_user: User = Depends(get_current_user)):
    """列出所有共享 (SMB/NFS)"""
    smb_shares = smb_manager.list_shares()
    nfs_shares = nfs_manager.list_shares()
    
    return {
        "smb": [asdict(s) for s in smb_shares],
        "nfs": [asdict(s) for s in nfs_shares]
    }


@smb_router.post("")
async def create_smb_share(
    name: str = Form(...),
    path: str = Form(...),
    comment: str = Form(""),
    writable: bool = Form(True),
    guest_ok: bool = Form(False),
    valid_users: str = Form(""),
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


@smb_router.delete("/{name}")
async def delete_smb_share(name: str, current_user: User = Depends(get_current_user)):
    """删除 SMB 共享"""
    result = smb_manager.delete_share(name)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


nfs_router = APIRouter(prefix="/api/v1/shares/nfs", tags=["NFS共享"])


@nfs_router.post("")
async def create_nfs_share(
    path: str = Form(...),
    clients: str = Form("*"),
    options: str = Form("rw,sync,no_subtree_check,no_root_squash"),
    comment: str = Form(""),
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


@nfs_router.delete("/{path}")
async def delete_nfs_share(path: str, current_user: User = Depends(get_current_user)):
    """删除 NFS 共享"""
    import urllib.parse
    path = urllib.parse.unquote(path)
    
    result = nfs_manager.delete_share(path)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


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