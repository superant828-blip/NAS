"""
相册服务 - 提取相册管理业务逻辑
"""
import os
import sqlite3
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from core.logging import logger


class AlbumService:
    """相册管理服务"""
    
    def __init__(self, db_path: str, upload_dir: Path):
        self.db_path = db_path
        self.upload_dir = upload_dir
    
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def list_albums(self, user_id: int) -> List[Dict]:
        """列出相册"""
        conn = self._get_db()
        try:
            cursor = conn.execute(
                """SELECT a.*, COUNT(p.id) as photo_count 
                   FROM albums a 
                   LEFT JOIN photos p ON a.id = p.album_id 
                   WHERE a.user_id = ? 
                   GROUP BY a.id 
                   ORDER BY a.created_at DESC""",
                (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_album(self, album_id: int, user_id: int) -> Optional[Dict]:
        """获取相册详情"""
        conn = self._get_db()
        try:
            cursor = conn.execute(
                "SELECT * FROM albums WHERE id = ? AND user_id = ?",
                (album_id, user_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def create_album(self, user_id: int, name: str, description: str = "") -> int:
        """创建相册"""
        conn = self._get_db()
        try:
            cursor = conn.execute(
                "INSERT INTO albums (user_id, name, description) VALUES (?, ?, ?)",
                (user_id, name, description)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def delete_album(self, album_id: int, user_id: int) -> bool:
        """删除相册"""
        conn = self._get_db()
        try:
            # 获取相册所有照片
            cursor = conn.execute(
                "SELECT stored_name FROM photos WHERE album_id = ? AND user_id = ?",
                (album_id, user_id)
            )
            photos = cursor.fetchall()
            
            # 删除物理文件
            for photo in photos:
                photo_path = self.upload_dir / "photos" / photo['stored_name']
                if photo_path.exists():
                    photo_path.unlink()
                
                # 删除缩略图
                thumb_path = self.upload_dir / "thumbs" / photo['stored_name']
                if thumb_path.exists():
                    thumb_path.unlink()
            
            # 删除数据库记录
            conn.execute("DELETE FROM photos WHERE album_id = ? AND user_id = ?", (album_id, user_id))
            conn.execute("DELETE FROM albums WHERE id = ? AND user_id = ?", (album_id, user_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def add_photo(self, user_id: int, album_id: int, original_name: str, 
                  stored_name: str, size: int, mime_type: str,
                  width: int = 0, height: int = 0) -> int:
        """添加照片到相册"""
        conn = self._get_db()
        try:
            path = f"photos/{stored_name}"
            thumb_path = f"thumbs/{stored_name}"
            
            cursor = conn.execute(
                """INSERT INTO photos (user_id, album_id, original_name, stored_name, path, thumbnail_path, size, mime_type, width, height)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, album_id, original_name, stored_name, path, thumb_path, size, mime_type, width, height)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def list_photos(self, album_id: int, user_id: int) -> List[Dict]:
        """列出相册照片"""
        conn = self._get_db()
        try:
            cursor = conn.execute(
                "SELECT * FROM photos WHERE album_id = ? AND user_id = ? ORDER BY uploaded_at DESC",
                (album_id, user_id)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


# 全局实例
album_service: Optional[AlbumService] = None
