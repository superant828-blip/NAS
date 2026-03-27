"""
系统插件 - 系统状态、缓存管理、密码检查
"""
from fastapi import APIRouter, Depends, HTTPException

from security.auth import auth_manager, User
from storage.zfs import zfs_manager
from share.smb import smb_manager
from share.nfs import nfs_manager
from core.cache import get_cache_stats, invalidate_cache


# ==================== 路由配置 ====================

router = APIRouter(tags=["系统"])


# ==================== 依赖注入 ====================

def get_current_user(authorization: str = None) -> User:
    """获取当前用户 - 从Header获取"""
    from fastapi import Header
    authorization = Header(None)
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


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return current_user


# ==================== 系统状态 ====================

@router.get("/api/v1/system/status")
async def get_system_status(current_user: User = Depends(get_current_user)):
    """获取系统状态"""
    pools = zfs_manager.list_pools()
    smb_status = smb_manager.get_status()
    nfs_status = nfs_manager.get_status()
    
    return {
        "pools": len(pools),
        "smb": smb_status,
        "nfs": nfs_status,
        "users": len(auth_manager.list_users())
    }


# ==================== 缓存管理 ====================

@router.get("/api/v1/cache/stats")
async def get_cache_stats_endpoint(current_user: User = Depends(get_current_user)):
    """获取缓存统计"""
    return get_cache_stats()


@router.post("/api/v1/cache/clear")
async def clear_cache(
    pattern: str = None,
    current_user: User = Depends(require_admin)
):
    """清除缓存"""
    count = invalidate_cache(pattern)
    return {"message": f"Cleared {count} cache entries"}