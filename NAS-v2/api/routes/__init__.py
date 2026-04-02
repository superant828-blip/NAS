"""
API 路由模块
"""
from fastapi import APIRouter

# 导入各路由模块
from .auth import router as auth_router
from .files import router as files_router
from .photos import router as photos_router
from .shares import router as shares_router
from .storage import router as storage_router
from .system import router as system_router
from .agents import router as agents_router

__all__ = [
    "auth_router",
    "files_router", 
    "photos_router",
    "shares_router",
    "storage_router",
    "system_router",
    "agents_router",
]
