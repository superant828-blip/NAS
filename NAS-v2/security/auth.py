"""
安全认证模块
支持 SQLite 和 MySQL
融合 NAS 项目的数据表结构
"""
import os
import secrets
import pymysql
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, List
from contextlib import contextmanager

import jwt
from passlib.hash import bcrypt

# 导入配置
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import config


@dataclass
class User:
    """用户信息"""
    id: int
    username: str
    email: str
    password_hash: str
    role: str  # admin, user
    created_at: str
    last_login: Optional[str] = None
    enabled: bool = True
    
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass  
class Session:
    """用户会话"""
    token: str
    user_id: int
    username: str
    created_at: datetime
    expires_at: datetime


# ==================== 新增数据模型 ====================

@dataclass
class Share:
    """分享链接"""
    id: int
    user_id: int
    file_type: str  # photo, file
    file_id: int
    token: str
    password_hash: Optional[str] = None
    salt: Optional[str] = None
    expire_hours: int = 24
    view_count: int = 0
    is_active: bool = True
    created_at: str = ""
    expires_at: Optional[str] = None


@dataclass
class Album:
    """相册"""
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    is_encrypted: bool = False
    password_hash: Optional[str] = None
    cover_url: Optional[str] = None
    created_at: str = ""


@dataclass
class Photo:
    """照片"""
    id: int
    user_id: int
    album_id: Optional[int] = None
    original_name: str = ""
    stored_name: str = ""
    path: str = ""
    thumbnail_path: Optional[str] = None
    size: int = 0
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    uploaded_at: str = ""


@dataclass
class Trash:
    """回收站"""
    id: int
    user_id: int
    file_type: str  # photo, file, folder
    original_id: int
    original_name: str
    stored_path: Optional[str] = None
    size: int = 0
    mime_type: Optional[str] = None
    deleted_at: str = ""


@dataclass
class Stats:
    """用户统计"""
    user_id: int
    albums_count: int = 0
    photos_count: int = 0
    files_count: int = 0
    folders_count: int = 0
    storage_used: int = 0
    shares_count: int = 0
    trash_count: int = 0


class AuthManager:
    """认证管理器"""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or os.urandom(32).hex()
        self.sessions: Dict[str, Session] = {}
        self._init_db()
    
    def _get_connection(self):
        """获取数据库连接"""
        if config.db_type == "mysql":
            return pymysql.connect(
                host=config.mysql_host,
                port=config.mysql_port,
                user=config.mysql_user,
                password=config.mysql_password,
                database=config.mysql_database,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True
            )
        else:
            # SQLite
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            conn.row_factory = sqlite3.Row
            return conn
    
    @contextmanager
    def _get_db(self):
        """获取数据库连接（上下文管理器）"""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库"""
        if config.db_type == "mysql":
            # 先连接到 MySQL 服务器（不指定数据库）
            conn = pymysql.connect(
                host=config.mysql_host,
                port=config.mysql_port,
                user=config.mysql_user,
                password=config.mysql_password
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.mysql_database}")
                    cursor.execute(f"USE {config.mysql_database}")
                    
                    # 现有表
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(255) UNIQUE NOT NULL,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL,
                            role VARCHAR(50) DEFAULT 'user',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP NULL,
                            enabled TINYINT DEFAULT 1
                        )
                    """)
                    
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS groups (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            name VARCHAR(255) UNIQUE NOT NULL,
                            description TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS user_groups (
                            user_id INT,
                            group_id INT,
                            PRIMARY KEY (user_id, group_id)
                        )
                    """)
                    
                    # ============ 新增表：分享链接 ============
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS shares (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT NOT NULL,
                            file_type VARCHAR(20) NOT NULL,
                            file_id INT NOT NULL,
                            token VARCHAR(64) UNIQUE NOT NULL,
                            password_hash VARCHAR(255),
                            salt VARCHAR(32),
                            expire_hours INT DEFAULT 24,
                            view_count INT DEFAULT 0,
                            is_active TINYINT DEFAULT 1,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expires_at TIMESTAMP NULL,
                            INDEX idx_user_id (user_id),
                            INDEX idx_token (token)
                        )
                    """)
                    
                    # ============ 新增表：相册 ============
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS albums (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT NOT NULL,
                            name VARCHAR(100) NOT NULL,
                            description TEXT,
                            is_encrypted TINYINT DEFAULT 0,
                            password_hash VARCHAR(255),
                            cover_url VARCHAR(500),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_user_id (user_id)
                        )
                    """)
                    
                    # ============ 新增表：照片 ============
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS photos (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT NOT NULL,
                            album_id INT,
                            original_name VARCHAR(255) NOT NULL,
                            stored_name VARCHAR(255) UNIQUE NOT NULL,
                            path VARCHAR(500) NOT NULL,
                            thumbnail_path VARCHAR(500),
                            size INT DEFAULT 0,
                            mime_type VARCHAR(100),
                            width INT,
                            height INT,
                            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_user_id (user_id),
                            INDEX idx_album_id (album_id)
                        )
                    """)
                    
                    # ============ 新增表：回收站 ============
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS trash (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT NOT NULL,
                            file_type VARCHAR(20) NOT NULL,
                            original_id INT NOT NULL,
                            original_name VARCHAR(255) NOT NULL,
                            stored_path VARCHAR(500),
                            size INT DEFAULT 0,
                            mime_type VARCHAR(100),
                            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_user_id (user_id)
                        )
                    """)
                    
                    # ============ 新增表：用户统计 ============
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS stats (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT NOT NULL UNIQUE,
                            albums_count INT DEFAULT 0,
                            photos_count INT DEFAULT 0,
                            files_count INT DEFAULT 0,
                            folders_count INT DEFAULT 0,
                            storage_used BIGINT DEFAULT 0,
                            shares_count INT DEFAULT 0,
                            trash_count INT DEFAULT 0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX idx_user_id (user_id)
                        )
                    """)
                    
                conn.commit()
            finally:
                conn.close()
            
            # 创建默认管理员
            self._create_default_admin_mysql()
        else:
            # SQLite
            import sqlite3
            os.makedirs(os.path.dirname(config.db_path) or ".", exist_ok=True)
            conn = sqlite3.connect(config.db_path)
            try:
                # 现有表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT DEFAULT 'user',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        last_login TEXT,
                        enabled INTEGER DEFAULT 1
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_groups (
                        user_id INTEGER,
                        group_id INTEGER,
                        PRIMARY KEY (user_id, group_id)
                    )
                """)
                
                # ============ 新增表：分享链接 ============
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS shares (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        file_type VARCHAR(20) NOT NULL,
                        file_id INTEGER NOT NULL,
                        token VARCHAR(64) UNIQUE NOT NULL,
                        password_hash TEXT,
                        salt VARCHAR(32),
                        expire_hours INTEGER DEFAULT 24,
                        view_count INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        expires_at TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shares_user_id ON shares(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shares_token ON shares(token)")
                
                # ============ 新增表：相册 ============
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS albums (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        is_encrypted INTEGER DEFAULT 0,
                        password_hash TEXT,
                        cover_url VARCHAR(500),
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_albums_user_id ON albums(user_id)")
                
                # ============ 新增表：照片 ============
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS photos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        album_id INTEGER,
                        original_name VARCHAR(255) NOT NULL,
                        stored_name VARCHAR(255) UNIQUE NOT NULL,
                        path VARCHAR(500) NOT NULL,
                        thumbnail_path VARCHAR(500),
                        size INTEGER DEFAULT 0,
                        mime_type VARCHAR(100),
                        width INTEGER,
                        height INTEGER,
                        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_album_id ON photos(album_id)")
                
                # ============ 新增表：回收站 ============
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trash (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        file_type VARCHAR(20) NOT NULL,
                        original_id INTEGER NOT NULL,
                        original_name VARCHAR(255) NOT NULL,
                        stored_path VARCHAR(500),
                        size INTEGER DEFAULT 0,
                        mime_type VARCHAR(100),
                        deleted_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trash_user_id ON trash(user_id)")
                
                # ============ 新增表：用户统计 ============
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        albums_count INTEGER DEFAULT 0,
                        photos_count INTEGER DEFAULT 0,
                        files_count INTEGER DEFAULT 0,
                        folders_count INTEGER DEFAULT 0,
                        storage_used INTEGER DEFAULT 0,
                        shares_count INTEGER DEFAULT 0,
                        trash_count INTEGER DEFAULT 0,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_stats_user_id ON stats(user_id)")
                
                conn.commit()
                
                # 创建默认管理员
                self._create_default_admin_sqlite(conn)
            finally:
                conn.close()
    
    def _create_default_admin_mysql(self):
        """MySQL: 创建默认管理员"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE role = 'admin'")
                if not cursor.fetchone():
                    admin_hash = bcrypt.hash("admin123")
                    cursor.execute(
                        "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                        ("admin", "admin@nas.local", admin_hash, "admin")
                    )
                    conn.commit()
        finally:
            conn.close()
    
    def _create_default_admin_sqlite(self, conn):
        """SQLite: 创建默认管理员"""
        cursor = conn.execute("SELECT id FROM users WHERE role = 'admin'")
        if not cursor.fetchone():
            admin_hash = bcrypt.hash("admin123")
            conn.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("admin", "admin@nas.local", admin_hash, "admin")
            )
            conn.commit()
    
    def create_user(self, username: str, email: str, password: str, role: str = "user") -> Dict:
        """创建用户"""
        if not username or not email or not password:
            return {"status": "error", "message": "Missing required fields"}
        
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM users WHERE username = %s OR email = %s",
                        (username, email)
                    )
                    if cursor.fetchone():
                        return {"status": "error", "message": "Username or email already exists"}
                    
                    password_hash = bcrypt.hash(password)
                    cursor.execute(
                        "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                        (username, email, password_hash, role)
                    )
                    conn.commit()
                    
                    return {
                        "status": "success",
                        "user": {"username": username, "email": email, "role": role}
                    }
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute(
                    "SELECT id FROM users WHERE username = ? OR email = ?",
                    (username, email)
                )
                if cursor.fetchone():
                    return {"status": "error", "message": "Username or email already exists"}
                
                password_hash = bcrypt.hash(password)
                conn.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (username, email, password_hash, role)
                )
                conn.commit()
                
                return {
                    "status": "success",
                    "user": {"username": username, "email": email, "role": role}
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def delete_user(self, user_id: int) -> Dict:
        """删除用户"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                    row = cursor.fetchone()
                    if row and row['role'] == 'admin':
                        return {"status": "error", "message": "Cannot delete admin user"}
                    
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    conn.commit()
                    return {"status": "success", "user_id": user_id}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                if row and row[0] == 'admin':
                    return {"status": "error", "message": "Cannot delete admin user"}
                
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                return {"status": "success", "user_id": user_id}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def list_users(self) -> List[User]:
        """列出所有用户"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, username, email, password_hash, role, created_at, last_login, enabled 
                        FROM users ORDER BY created_at DESC
                    """)
                    rows = cursor.fetchall()
                    return [User(
                        id=r['id'],
                        username=r['username'],
                        email=r['email'],
                        password_hash=r['password_hash'],
                        role=r['role'],
                        created_at=str(r['created_at']) if r['created_at'] else "",
                        last_login=str(r['last_login']) if r['last_login'] else None,
                        enabled=bool(r['enabled'])
                    ) for r in rows]
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("""
                    SELECT id, username, email, password_hash, role, created_at, last_login, enabled 
                    FROM users ORDER BY created_at DESC
                """)
                return [User(*row) for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def get_user(self, user_id: int = None, username: str = None, email: str = None) -> Optional[User]:
        """获取用户"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    if user_id:
                        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                    elif username:
                        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                    elif email:
                        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                    else:
                        return None
                    
                    row = cursor.fetchone()
                    if row:
                        return User(
                            id=row['id'],
                            username=row['username'],
                            email=row['email'],
                            password_hash=row['password_hash'],
                            role=row['role'],
                            created_at=str(row['created_at']) if row['created_at'] else "",
                            last_login=str(row['last_login']) if row['last_login'] else None,
                            enabled=bool(row['enabled'])
                        )
                    return None
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                if user_id:
                    cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                elif username:
                    cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
                elif email:
                    cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
                else:
                    return None
                
                row = cursor.fetchone()
                if row:
                    return User(*row)
                return None
            finally:
                conn.close()
    
    def authenticate(self, login: str, password: str) -> Optional[User]:
        """验证用户登录"""
        user = self.get_user(username=login) or self.get_user(email=login)
        
        if not user or not user.enabled:
            return None
        
        if bcrypt.verify(password, user.password_hash):
            # 更新最后登录时间
            now = datetime.now().isoformat()
            if config.db_type == "mysql":
                conn = self._get_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", (now, user.id))
                        conn.commit()
                finally:
                    conn.close()
            else:
                import sqlite3
                conn = sqlite3.connect(config.db_path)
                try:
                    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user.id))
                    conn.commit()
                finally:
                    conn.close()
            return user
        
        return None
    
    def create_session(self, user: User) -> str:
        """创建会话"""
        token = secrets.token_urlsafe(32)
        now = datetime.now()
        expires = now + timedelta(hours=24)
        
        session = Session(
            token=token,
            user_id=user.id,
            username=user.username,
            created_at=now,
            expires_at=expires
        )
        self.sessions[token] = session
        
        return token
    
    def validate_session(self, token: str) -> Optional[User]:
        """验证会话"""
        session = self.sessions.get(token)
        
        if not session:
            return None
        
        if session.expires_at < datetime.now():
            del self.sessions[token]
            return None
        
        return self.get_user(user_id=session.user_id)
    
    def destroy_session(self, token: str):
        """销毁会话"""
        if token in self.sessions:
            del self.sessions[token]
    
    def create_token(self, user: User, expires_hours: int = 24) -> str:
        """创建 JWT token"""
        payload = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "exp": datetime.now() + timedelta(hours=expires_hours)
        }
        
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """验证 JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> Dict:
        """修改密码"""
        user = self.get_user(user_id=user_id)
        if not user:
            return {"status": "error", "message": "User not found"}
        
        if not bcrypt.verify(old_password, user.password_hash):
            return {"status": "error", "message": "Invalid old password"}
        
        new_hash = bcrypt.hash(new_password)
        
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def set_user_enabled(self, user_id: int, enabled: bool) -> Dict:
        """启用/禁用用户"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE users SET enabled = %s WHERE id = %s", (1 if enabled else 0, user_id))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("UPDATE users SET enabled = ? WHERE id = ?", (1 if enabled else 0, user_id))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()

    # ==================== 分享链接 CRUD ====================
    
    def create_share(self, user_id: int, file_type: str, file_id: int, 
                     password: str = None, expire_hours: int = 24) -> Dict:
        """创建分享链接"""
        token = secrets.token_urlsafe(32)
        password_hash = None
        salt = None
        
        if password:
            salt = secrets.token_hex(16)
            password_hash = bcrypt.hash(password)
        
        expires_at = datetime.now() + timedelta(hours=expire_hours) if expire_hours else None
        
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO shares (user_id, file_type, file_id, token, password_hash, salt, expire_hours, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (user_id, file_type, file_id, token, password_hash, salt, expire_hours, expires_at))
                    conn.commit()
                    return {"status": "success", "token": token, "share_url": f"/share/{token}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("""
                    INSERT INTO shares (user_id, file_type, file_id, token, password_hash, salt, expire_hours, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, file_type, file_id, token, password_hash, salt, expire_hours, 
                      expires_at.isoformat() if expires_at else None))
                conn.commit()
                return {"status": "success", "token": token, "share_url": f"/share/{token}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def get_share(self, token: str) -> Optional[Share]:
        """获取分享链接"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM shares WHERE token = %s", (token,))
                    row = cursor.fetchone()
                    if row:
                        return Share(
                            id=row['id'], user_id=row['user_id'], file_type=row['file_type'],
                            file_id=row['file_id'], token=row['token'], 
                            password_hash=row.get('password_hash'), salt=row.get('salt'),
                            expire_hours=row['expire_hours'], view_count=row['view_count'],
                            is_active=bool(row['is_active']),
                            created_at=str(row['created_at']) if row['created_at'] else "",
                            expires_at=str(row['expires_at']) if row.get('expires_at') else None
                        )
                    return None
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("SELECT * FROM shares WHERE token = ?", (token,))
                row = cursor.fetchone()
                if row:
                    return Share(*row)
                return None
            finally:
                conn.close()
    
    def list_user_shares(self, user_id: int) -> List[Share]:
        """列出用户的分享链接"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM shares WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
                    rows = cursor.fetchall()
                    return [Share(
                        id=r['id'], user_id=r['user_id'], file_type=r['file_type'],
                        file_id=r['file_id'], token=r['token'], 
                        password_hash=r.get('password_hash'), salt=r.get('salt'),
                        expire_hours=r['expire_hours'], view_count=r['view_count'],
                        is_active=bool(r['is_active']),
                        created_at=str(r['created_at']) if r['created_at'] else "",
                        expires_at=str(r['expires_at']) if r.get('expires_at') else None
                    ) for r in rows]
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("SELECT * FROM shares WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
                return [Share(*row) for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def delete_share(self, share_id: int, user_id: int) -> Dict:
        """删除分享链接"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM shares WHERE id = %s AND user_id = %s", (share_id, user_id))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("DELETE FROM shares WHERE id = ? AND user_id = ?", (share_id, user_id))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def increment_share_view_count(self, token: str) -> Dict:
        """增加分享访问计数"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE shares SET view_count = view_count + 1 WHERE token = %s", (token,))
                    conn.commit()
                    return {"status": "success"}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("UPDATE shares SET view_count = view_count + 1 WHERE token = ?", (token,))
                conn.commit()
                return {"status": "success"}
            finally:
                conn.close()

    # ==================== 相册 CRUD ====================
    
    def create_album(self, user_id: int, name: str, description: str = None, 
                     is_encrypted: bool = False, password: str = None) -> Dict:
        """创建相册"""
        password_hash = bcrypt.hash(password) if password else None
        
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO albums (user_id, name, description, is_encrypted, password_hash)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, name, description, 1 if is_encrypted else 0, password_hash))
                    conn.commit()
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    album_id = cursor.fetchone()[0]
                    return {"status": "success", "album_id": album_id, "name": name}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("""
                    INSERT INTO albums (user_id, name, description, is_encrypted, password_hash)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, name, description, 1 if is_encrypted else 0, password_hash))
                conn.commit()
                return {"status": "success", "album_id": cursor.lastrowid, "name": name}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def get_album(self, album_id: int, user_id: int = None) -> Optional[Album]:
        """获取相册"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    if user_id:
                        cursor.execute("SELECT * FROM albums WHERE id = %s AND user_id = %s", (album_id, user_id))
                    else:
                        cursor.execute("SELECT * FROM albums WHERE id = %s", (album_id,))
                    row = cursor.fetchone()
                    if row:
                        return Album(
                            id=row['id'], user_id=row['user_id'], name=row['name'],
                            description=row.get('description'), 
                            is_encrypted=bool(row['is_encrypted']),
                            password_hash=row.get('password_hash'),
                            cover_url=row.get('cover_url'),
                            created_at=str(row['created_at']) if row['created_at'] else ""
                        )
                    return None
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                if user_id:
                    cursor = conn.execute("SELECT * FROM albums WHERE id = ? AND user_id = ?", (album_id, user_id))
                else:
                    cursor = conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,))
                row = cursor.fetchone()
                if row:
                    return Album(*row)
                return None
            finally:
                conn.close()
    
    def list_user_albums(self, user_id: int) -> List[Album]:
        """列出用户相册"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM albums WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
                    rows = cursor.fetchall()
                    return [Album(
                        id=r['id'], user_id=r['user_id'], name=r['name'],
                        description=r.get('description'), 
                        is_encrypted=bool(r['is_encrypted']),
                        password_hash=r.get('password_hash'),
                        cover_url=r.get('cover_url'),
                        created_at=str(r['created_at']) if r['created_at'] else ""
                    ) for r in rows]
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("SELECT * FROM albums WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
                return [Album(*row) for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def update_album(self, album_id: int, user_id: int, name: str = None, 
                     description: str = None, cover_url: str = None) -> Dict:
        """更新相册"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    updates = []
                    params = []
                    if name:
                        updates.append("name = %s")
                        params.append(name)
                    if description is not None:
                        updates.append("description = %s")
                        params.append(description)
                    if cover_url:
                        updates.append("cover_url = %s")
                        params.append(cover_url)
                    
                    if updates:
                        params.extend([album_id, user_id])
                        cursor.execute(f"UPDATE albums SET {', '.join(updates)} WHERE id = %s AND user_id = %s", params)
                        conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                updates = []
                params = []
                if name:
                    updates.append("name = ?")
                    params.append(name)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                if cover_url:
                    updates.append("cover_url = ?")
                    params.append(cover_url)
                
                if updates:
                    params.extend([album_id, user_id])
                    conn.execute(f"UPDATE albums SET {', '.join(updates)} WHERE id = ? AND user_id = ?", params)
                    conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def delete_album(self, album_id: int, user_id: int) -> Dict:
        """删除相册"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    # 先删除相册中的照片
                    cursor.execute("DELETE FROM photos WHERE album_id = %s AND user_id = %s", (album_id, user_id))
                    # 再删除相册
                    cursor.execute("DELETE FROM albums WHERE id = %s AND user_id = %s", (album_id, user_id))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("DELETE FROM photos WHERE album_id = ? AND user_id = ?", (album_id, user_id))
                conn.execute("DELETE FROM albums WHERE id = ? AND user_id = ?", (album_id, user_id))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()

    # ==================== 照片 CRUD ====================
    
    def add_photo(self, user_id: int, original_name: str, stored_name: str, path: str,
                  size: int = 0, mime_type: str = None, album_id: int = None,
                  width: int = None, height: int = None, thumbnail_path: str = None) -> Dict:
        """添加照片"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO photos (user_id, album_id, original_name, stored_name, path, thumbnail_path, size, mime_type, width, height)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (user_id, album_id, original_name, stored_name, path, thumbnail_path, size, mime_type, width, height))
                    conn.commit()
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    photo_id = cursor.fetchone()[0]
                    return {"status": "success", "photo_id": photo_id}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("""
                    INSERT INTO photos (user_id, album_id, original_name, stored_name, path, thumbnail_path, size, mime_type, width, height)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, album_id, original_name, stored_name, path, thumbnail_path, size, mime_type, width, height))
                conn.commit()
                return {"status": "success", "photo_id": cursor.lastrowid}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def get_photo(self, photo_id: int, user_id: int = None) -> Optional[Photo]:
        """获取照片"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    if user_id:
                        cursor.execute("SELECT * FROM photos WHERE id = %s AND user_id = %s", (photo_id, user_id))
                    else:
                        cursor.execute("SELECT * FROM photos WHERE id = %s", (photo_id,))
                    row = cursor.fetchone()
                    if row:
                        return Photo(
                            id=row['id'], user_id=row['user_id'], album_id=row.get('album_id'),
                            original_name=row['original_name'], stored_name=row['stored_name'],
                            path=row['path'], thumbnail_path=row.get('thumbnail_path'),
                            size=row['size'], mime_type=row.get('mime_type'),
                            width=row.get('width'), height=row.get('height'),
                            uploaded_at=str(row['uploaded_at']) if row['uploaded_at'] else ""
                        )
                    return None
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                if user_id:
                    cursor = conn.execute("SELECT * FROM photos WHERE id = ? AND user_id = ?", (photo_id, user_id))
                else:
                    cursor = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
                row = cursor.fetchone()
                if row:
                    return Photo(*row)
                return None
            finally:
                conn.close()
    
    def list_user_photos(self, user_id: int, album_id: int = None, limit: int = 50, offset: int = 0) -> List[Photo]:
        """列出用户照片"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    if album_id:
                        cursor.execute("""
                            SELECT * FROM photos WHERE user_id = %s AND album_id = %s 
                            ORDER BY uploaded_at DESC LIMIT %s OFFSET %s
                        """, (user_id, album_id, limit, offset))
                    else:
                        cursor.execute("""
                            SELECT * FROM photos WHERE user_id = %s 
                            ORDER BY uploaded_at DESC LIMIT %s OFFSET %s
                        """, (user_id, limit, offset))
                    rows = cursor.fetchall()
                    return [Photo(
                        id=r['id'], user_id=r['user_id'], album_id=r.get('album_id'),
                        original_name=r['original_name'], stored_name=r['stored_name'],
                        path=r['path'], thumbnail_path=r.get('thumbnail_path'),
                        size=r['size'], mime_type=r.get('mime_type'),
                        width=r.get('width'), height=r.get('height'),
                        uploaded_at=str(r['uploaded_at']) if r['uploaded_at'] else ""
                    ) for r in rows]
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                if album_id:
                    cursor = conn.execute("""
                        SELECT * FROM photos WHERE user_id = ? AND album_id = ? 
                        ORDER BY uploaded_at DESC LIMIT ? OFFSET ?
                    """, (user_id, album_id, limit, offset))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM photos WHERE user_id = ? 
                        ORDER BY uploaded_at DESC LIMIT ? OFFSET ?
                    """, (user_id, limit, offset))
                return [Photo(*row) for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def move_photo_to_album(self, photo_id: int, user_id: int, album_id: int = None) -> Dict:
        """移动照片到相册"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE photos SET album_id = %s WHERE id = %s AND user_id = %s", 
                                   (album_id, photo_id, user_id))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("UPDATE photos SET album_id = ? WHERE id = ? AND user_id = ?", 
                             (album_id, photo_id, user_id))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def delete_photo(self, photo_id: int, user_id: int) -> Dict:
        """删除照片"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM photos WHERE id = %s AND user_id = %s", (photo_id, user_id))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("DELETE FROM photos WHERE id = ? AND user_id = ?", (photo_id, user_id))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()

    # ==================== 回收站 CRUD ====================
    
    def add_to_trash(self, user_id: int, file_type: str, original_id: int, 
                     original_name: str, stored_path: str = None, size: int = 0, 
                     mime_type: str = None) -> Dict:
        """添加到回收站"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO trash (user_id, file_type, original_id, original_name, stored_path, size, mime_type)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (user_id, file_type, original_id, original_name, stored_path, size, mime_type))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("""
                    INSERT INTO trash (user_id, file_type, original_id, original_name, stored_path, size, mime_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, file_type, original_id, original_name, stored_path, size, mime_type))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def get_trash_items(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Trash]:
        """获取回收站列表"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT * FROM trash WHERE user_id = %s 
                        ORDER BY deleted_at DESC LIMIT %s OFFSET %s
                    """, (user_id, limit, offset))
                    rows = cursor.fetchall()
                    return [Trash(
                        id=r['id'], user_id=r['user_id'], file_type=r['file_type'],
                        original_id=r['original_id'], original_name=r['original_name'],
                        stored_path=r.get('stored_path'), size=r['size'], 
                        mime_type=r.get('mime_type'),
                        deleted_at=str(r['deleted_at']) if r['deleted_at'] else ""
                    ) for r in rows]
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                cursor = conn.execute("""
                    SELECT * FROM trash WHERE user_id = ? 
                    ORDER BY deleted_at DESC LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
                return [Trash(*row) for row in cursor.fetchall()]
            finally:
                conn.close()
    
    def restore_from_trash(self, trash_id: int, user_id: int) -> Dict:
        """从回收站恢复"""
        # 这里只删除回收站记录，实际文件恢复需要业务逻辑处理
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM trash WHERE id = %s AND user_id = %s", (trash_id, user_id))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("DELETE FROM trash WHERE id = ? AND user_id = ?", (trash_id, user_id))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
    
    def empty_trash(self, user_id: int) -> Dict:
        """清空回收站"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM trash WHERE user_id = %s", (user_id,))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("DELETE FROM trash WHERE user_id = ?", (user_id,))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()

    # ==================== 统计 CRUD ====================
    
    def get_user_stats(self, user_id: int) -> Stats:
        """获取用户统计"""
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    # 获取相册数
                    cursor.execute("SELECT COUNT(*) as count FROM albums WHERE user_id = %s", (user_id,))
                    albums_count = cursor.fetchone()['count'] or 0
                    
                    # 获取照片数
                    cursor.execute("SELECT COUNT(*) as count, COALESCE(SUM(size), 0) as size FROM photos WHERE user_id = %s", (user_id,))
                    photo_row = cursor.fetchone()
                    photos_count = photo_row['count'] or 0
                    photos_size = photo_row['size'] or 0
                    
                    # 获取分享数
                    cursor.execute("SELECT COUNT(*) as count FROM shares WHERE user_id = %s", (user_id,))
                    shares_count = cursor.fetchone()['count'] or 0
                    
                    # 获取回收站数量
                    cursor.execute("SELECT COUNT(*) as count FROM trash WHERE user_id = %s", (user_id,))
                    trash_count = cursor.fetchone()['count'] or 0
                    
                    return Stats(
                        user_id=user_id,
                        albums_count=albums_count,
                        photos_count=photos_count,
                        storage_used=photos_size,
                        shares_count=shares_count,
                        trash_count=trash_count
                    )
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                # 获取相册数
                cursor = conn.execute("SELECT COUNT(*) as count FROM albums WHERE user_id = ?", (user_id,))
                albums_count = cursor.fetchone()[0] or 0
                
                # 获取照片数
                cursor = conn.execute("SELECT COUNT(*) as count, COALESCE(SUM(size), 0) as size FROM photos WHERE user_id = ?", (user_id,))
                photo_row = cursor.fetchone()
                photos_count = photo_row[0] or 0
                photos_size = photo_row[1] or 0
                
                # 获取分享数
                cursor = conn.execute("SELECT COUNT(*) as count FROM shares WHERE user_id = ?", (user_id,))
                shares_count = cursor.fetchone()[0] or 0
                
                # 获取回收站数量
                cursor = conn.execute("SELECT COUNT(*) as count FROM trash WHERE user_id = ?", (user_id,))
                trash_count = cursor.fetchone()[0] or 0
                
                return Stats(
                    user_id=user_id,
                    albums_count=albums_count,
                    photos_count=photos_count,
                    storage_used=photos_size,
                    shares_count=shares_count,
                    trash_count=trash_count
                )
            finally:
                conn.close()
    
    def update_user_stats(self, user_id: int) -> Dict:
        """更新用户统计缓存"""
        stats = self.get_user_stats(user_id)
        
        if config.db_type == "mysql":
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO stats (user_id, albums_count, photos_count, storage_used, shares_count, trash_count)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            albums_count = %s, photos_count = %s, storage_used = %s, 
                            shares_count = %s, trash_count = %s
                    """, (user_id, stats.albums_count, stats.photos_count, stats.storage_used, 
                          stats.shares_count, stats.trash_count,
                          stats.albums_count, stats.photos_count, stats.storage_used,
                          stats.shares_count, stats.trash_count))
                    conn.commit()
                    return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            try:
                conn.execute("""
                    INSERT INTO stats (user_id, albums_count, photos_count, storage_used, shares_count, trash_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET 
                        albums_count = excluded.albums_count, 
                        photos_count = excluded.photos_count, 
                        storage_used = excluded.storage_used,
                        shares_count = excluded.shares_count,
                        trash_count = excluded.trash_count
                """, (user_id, stats.albums_count, stats.photos_count, stats.storage_used, 
                      stats.shares_count, stats.trash_count))
                conn.commit()
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                conn.close()


# 全局认证管理器
auth_manager = AuthManager()