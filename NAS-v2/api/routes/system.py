"""
系统管理路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/system", tags=["系统管理"])


@router.get("/status")
async def get_system_status():
    """获取系统状态"""
    import psutil
    import time
    
    return {
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "uptime": int(time.time() - psutil.boot_time())
    }


@router.get("/stats")
async def get_stats():
    """获取统计信息"""
    pass


# 缓存管理
@router.get("/cache/stats")
async def get_cache_stats():
    """获取缓存统计"""
    from core.cache import get_cache_stats
    return get_cache_stats()


@router.post("/cache/clear")
async def clear_cache():
    """清除缓存"""
    from core.cache import api_cache
    api_cache.clear()
    return {"message": "缓存已清除"}


# 密码验证
@router.get("/password/check")
async def check_password_strength(password: str):
    """检查密码强度"""
    from core.security import PasswordStrengthChecker
    checker = PasswordStrengthChecker()
    result = checker.check(password)
    return {
        "is_valid": result.is_valid,
        "score": result.score,
        "suggestions": result.suggestions
    }


# 健康检查
@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": None}