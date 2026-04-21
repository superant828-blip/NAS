"""
文件服务 - 提取文件管理业务逻辑
"""
import os
import sqlite3
import shutil
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.security import InputValidator, ValidationResult
from core.logging import logger


class FileService:
    """文件管理服务"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def list_files(self, user_id: int, parent_id: Optional[int] = None) -> List[Dict]:
        """列出文件"""
        conn = self._get_db()
        try:
            if parent_id is None:
                # 根目录
                cursor = conn.execute(
                    "SELECT * FROM files WHERE user_id = ? AND parent_id IS NULL AND status = 1 ORDER BY is_folder DESC, name",
                    (user_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM files WHERE user_id = ? AND parent_id = ? AND status = 1 ORDER BY is_folder DESC, name",
                    (user_id, parent_id)
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_file(self, file_id: int, user_id: int) -> Optional[Dict]:
        """获取文件详情"""
        conn = self._get_db()
        try:
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ? AND status = 1",
                (file_id, user_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def create_file(self, user_id: int, name: str, parent_id: Optional[int], 
                    is_folder: bool, path: str, size: int = 0, mime_type: str = "") -> int:
        """创建文件/文件夹"""
        # 验证文件名
        validation = InputValidator.validate_filename(name)
        if not validation.valid:
            raise ValueError(validation.message)
        
        conn = self._get_db()
        try:
            cursor = conn.execute(
                """INSERT INTO files (user_id, parent_id, name, is_folder, path, full_path, size, mime_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, parent_id, name, 1 if is_folder else 0, path, path, size, mime_type)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def delete_file(self, file_id: int, user_id: int) -> bool:
        """删除文件（软删除到回收站）"""
        conn = self._get_db()
        try:
            # 获取文件信息
            cursor = conn.execute(
                "SELECT * FROM files WHERE id = ? AND user_id = ?",
                (file_id, user_id)
            )
            file_info = cursor.fetchone()
            if not file_info:
                return False
            
            # 移动到回收站
            conn.execute(
                """INSERT INTO trash (user_id, file_type, original_id, original_name, stored_path, size, mime_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, 'file', file_id, file_info['name'], file_info['path'], file_info['size'], file_info['mime_type'])
            )
            
            # 软删除
            conn.execute(
                "UPDATE files SET status = 0 WHERE id = ?",
                (file_id,)
            )
            conn.commit()
            return True
        finally:
            conn.close()
    
    def search_files(self, user_id: int, query: str) -> List[Dict]:
        """搜索文件"""
        # 验证搜索词
        validation = InputValidator.validate_search_query(query)
        if not validation.valid:
            raise ValueError(validation.message)
        
        conn = self._get_db()
        try:
            # 转义 LIKE 特殊字符
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            cursor = conn.execute(
                "SELECT * FROM files WHERE user_id = ? AND status = 1 AND name LIKE ? ESCAPE '\\' LIMIT 50",
                (user_id, f'%{escaped}%')
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_path_chain(self, file_id: int, user_id: int) -> List[Dict]:
        """获取文件路径链（面包屑）"""
        chain = []
        conn = self._get_db()
        
        try:
            current_id = file_id
            while current_id:
                cursor = conn.execute(
                    "SELECT * FROM files WHERE id = ? AND user_id = ?",
                    (current_id, user_id)
                )
                row = cursor.fetchone()
                if not row:
                    break
                chain.append(dict(row))
                current_id = row['parent_id']
            
            return list(reversed(chain))
        finally:
            conn.close()


# 全局实例（需在 main.py 中初始化）
file_service: Optional[FileService] = None
