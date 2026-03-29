"""系统插件 - 系统状态、缓存管理"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header

from security.auth import auth_manager, User
from core.cache import get_cache_stats, invalidate_cache

router = APIRouter(prefix="/api/v1/system", tags=["系统"])


def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """获取当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    payload = auth_manager.verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = auth_manager.get_user(user_id=payload.get("user_id"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


@router.get("/status")
async def system_status(current_user: User = Depends(get_current_user)):
    """系统状态"""
    return {
        "status": "running",
        "version": "2.0.0",
        "storage_pools": 1,
        "datasets": 3,
        "snapshots": 0,
        "shares": 2,
        "users": 2
    }


@router.get("/cache/stats")
async def cache_stats(current_user: User = Depends(get_current_user)):
    """缓存统计"""
    stats = get_cache_stats()
    return stats


@router.post("/cache/clear")
async def clear_cache(current_user: User = Depends(get_current_user)):
    """清空缓存"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    
    invalidate_cache()
    return {"status": "success", "message": "Cache cleared"}
