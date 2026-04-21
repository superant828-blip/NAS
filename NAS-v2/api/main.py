"""
NAS API 主程序 - 重构版 (精简路由层)
基于 TrueNAS 架构的私有 NAS - 包含完整文件管理功能

重构原则 (CLAUDE.md):
- 简化优先: 业务逻辑提取到 services/
- 精准修改: 保持功能兼容
- 目标驱动: 验证核心功能正常
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

from fastapi import FastAPI, Depends, HTTPException, status, Header, UploadFile, File as FastAPIFile, Form, Request, Query
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

# 导入服务层
from api.services import FileService, file_service, AlbumService, album_service, ShareService, share_service

# 导入智能体路由
from api.routes.agents import router as agents_router

# 导入路由模块 (路由层重构)
from api.routes.auth import router as auth_router
from api.routes.files import router as files_router
from api.routes.photos import router as photos_router
from api.routes.shares import router as shares_router
from api.routes.storage import router as storage_router
from api.routes.system import router as system_router


# ==================== 配置 ====================
UPLOAD_DIR = Path("/nas-pool/data/uploads")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
for subdir in ['files', 'photos', 'thumbs']:
    (UPLOAD_DIR / subdir).mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'pdf', 'doc', 'docx', 'zip', 'rar', 'txt', 'mp3', 'wav', 'apk', 'exe', 'csv', 'xls', 'xlsx', 'ppt', 'pptx', 'json', 'xml', 'html', 'css', 'js', 'svg', 'ico', 'bmp', 'tiff', 'flac', 'aac', 'ogg', 'wma', 'mov', 'avi', 'mkv', 'wmv', 'flv', '7z', 'tar', 'gz', 'bz2', 'iso', 'dmg', 'img', 'bin'}

# 应用配置
import json
def load_app_config():
    config_file = ROOT / "data" / "app_config.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {"allowed_extensions": list(ALLOWED_EXTENSIONS)}

def save_app_config(config_data):
    config_file = ROOT / "data" / "app_config.json"
    config_file.write_text(json.dumps(config_data, ensure_ascii=False, indent=2))

APP_CONFIG = load_app_config()
if APP_CONFIG.get("allowed_extensions"):
    ALLOWED_EXTENSIONS = set(APP_CONFIG["allowed_extensions"])


# ==================== 数据库初始化 (提取到函数) ====================
def init_file_db():
    """初始化文件管理数据库"""
    import sqlite3
    db_path = ROOT / "data" / "files.db"
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # 文件表
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
    # 索引
    for idx in ['user_id', 'parent_id', 'status', 'name', 'user_status', 'user_parent']:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_files_{idx} ON files({idx.replace('_', ', ')})")
    
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
    
    # 照片表
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
    for idx in ['user_id', 'album_id', 'uploaded_at']:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_photos_{idx} ON photos({idx})")
    
    # 分享表
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
    for idx in ['user_id', 'token', 'file', 'expires']:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_shares_{idx} ON shares({idx.replace('_', ', ')})")
    
    # 回收站表
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trash_user ON trash(user_id, deleted_at)")
    
    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")
    return db_path

FILE_DB_PATH = init_file_db()


# ==================== 初始化服务层 ====================
def init_services():
    """初始化服务层"""
    global file_service, album_service, share_service
    
    file_service = FileService(str(FILE_DB_PATH))
    album_service = AlbumService(str(FILE_DB_PATH), UPLOAD_DIR)
    share_service = ShareService(str(FILE_DB_PATH))
    
    logger.info("服务层初始化完成")


# ==================== FastAPI 应用 ====================
app = FastAPI(
    title="NAS API",
    description="TrueNAS-style Private NAS System",
    version="2.0.1"  # 重构版本
)

# 插件系统
try:
    from api.plugins import get_routers
    for router in get_routers():
        app.include_router(router)
    print("✓ 插件系统加载成功")
except Exception as e:
    print(f"⚠ 插件加载失败: {e}")

# 路由注册
app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(files_router)
app.include_router(photos_router)
app.include_router(shares_router)
app.include_router(storage_router)
app.include_router(system_router)
print("✓ 模块化路由加载成功")

# 静态文件
from fastapi.staticfiles import StaticFiles
ui_path = ROOT / "ui"
if ui_path.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_path), html=True), name="ui")
    app.mount("/", StaticFiles(directory=str(ui_path), html=True), name="root_ui")
    
    js_path = ui_path / "js"
    if js_path.exists():
        app.mount("/js", StaticFiles(directory=str(js_path)), name="js")
    
    uploads_path = ROOT / "uploads"
    if uploads_path.exists():
        app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 异常处理 ====================
@app.exception_handler(NASException)
async def nas_exception_handler(request: Request, exc: NASException):
    logger.warning(f"[{exc.code}] {exc.message}")
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = [".".join(str(loc) for loc in e.get("loc", [])) + ": " + e.get("msg", "Invalid") for e in errors]
    logger.warning(f"Validation error: {messages}")
    return JSONResponse(status_code=400, content={"error": "VALIDATION_ERROR", "message": "请求参数验证失败", "details": messages})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = ErrorLogger.log_error(exc, {"method": request.method, "path": str(request.url), "client": request.client.host if request.client else None})
    logger.error(f"Unhandled exception [{error_id}]: {str(exc)}")
    return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR", "message": "服务器内部错误", "error_id": error_id})


# ==================== 请求日志中间件 ====================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    client_ip = request.client.host if request.client else None
    
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        ErrorLogger.log_access(method=request.method, path=str(request.url), status_code=response.status_code, duration_ms=duration_ms, ip=client_ip)
        
        if duration_ms > 3000:
            logger.warning(f"Slow request: {request.method} {request.url} took {duration_ms:.0f}ms")
        
        return response
    except Exception as e:
        logger.error(f"Request error: {e}")
        raise


# ==================== 根路径 ====================
@app.get("/", response_class=HTMLResponse)
async def root():
    ui_path = ROOT / "ui" / "index.html"
    if ui_path.exists():
        return HTMLResponse(content=ui_path.read_text())
    return HTMLResponse(content="<h1>NAS API v2.0.1 - Running</h1><p>Docs: <a href='/docs'>/docs</a></p>")


# ==================== 系统初始化 ====================
def init_systems():
    """初始化所有系统"""
    try:
        from api.init_agents import init_agent_system, init_tools
        init_agent_system()
        init_tools()
        init_services()  # 初始化服务层
    except Exception as e:
        print(f"⚠ 系统初始化失败: {e}")

init_systems()


# ==================== 启动 ====================
if __name__ == "__main__":
    import uvicorn
    
    print(f"""
╔═══════════════════════════════════════════════╗
║     NAS System v2.0.1 - 重构版                 ║
║                                               ║
║  功能: 文件管理 | ZFS存储 | SMB/NFS | 智能体   ║
║                                               ║
║  API:    http://localhost:{config.port}/api/v1    ║
║  Docs:   http://localhost:{config.port}/docs      ║
╚═══════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host=config.host, port=config.port)
