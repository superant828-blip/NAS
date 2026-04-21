"""
分享服务 - 提取文件分享业务逻辑
"""
import os
import sqlite3
import secrets
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from core.security import InputValidator
from core.logging import logger


class ShareService:
    """文件分享服务"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_share(self, user_id: int, file_type: str, file_id: int,
                     password: Optional[str] = None, expire_hours: int = 24) -> Dict:
        """创建分享链接"""
        token = secrets.token_urlsafe(32)
        password_hash = None
        
        if password:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        expire_at = (datetime.now() + timedelta(hours=expire_hours)).isoformat()
        
        conn = self._get_db()
        try:
            cursor = conn.execute(
                """INSERT INTO shares (user_id, file_type, file_id, token, password_hash, expire_hours, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, file_type, file_id, token, password_hash, expire_hours, expire_at)
            )
            conn.commit()
            
            return {
                "id": cursor.lastrowid,
                "token": token,
                "expires_at": expire_at
            }
        finally:
            conn.close()
    
    def get_share(self, token: str, password: Optional[str] = None) -> Optional[Dict]:
        """获取分享信息"""
        conn = self._get_db()
        try:
            cursor = conn.execute(
                "SELECT * FROM shares WHERE token = ? AND is_active = 1",
                (token,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # 检查过期
            if row['expires_at']:
                expires = datetime.fromisoformat(row['expires_at'])
                if expires < datetime.now():
                    return None
            
            # 检查密码
            if row['password_hash']:
                if not password:
                    return None
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                if password_hash != row['password_hash']:
                    return None
            
            # 增加访问计数
            conn.execute("UPDATE shares SET view_count = view_count + 1 WHERE id = ?", (row['id'],))
            conn.commit()
            
            return dict(row)
        finally:
            conn.close()
    
    def list_shares(self, user_id: int) -> List[Dict]:
        """列出用户的分享"""
        conn = self._get_db()
        try:
            cursor = conn.execute(
                "SELECT * FROM shares WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def delete_share(self, share_id: int, user_id: int) -> bool:
        """删除分享"""
        conn = self._get_db()
        try:
            conn.execute(
                "UPDATE shares SET is_active = 0 WHERE id = ? AND user_id = ?",
                (share_id, user_id)
            )
            conn.commit()
            return True
        finally:
            conn.close()
    
    def revoke_share(self, token: str) -> bool:
        """撤销分享"""
        conn = self._get_db()
        try:
            conn.execute("UPDATE shares SET is_active = 0 WHERE token = ?", (token,))
            conn.commit()
            return True
        finally:
            conn.close()


# 全局实例
share_service: Optional[ShareService] = None
