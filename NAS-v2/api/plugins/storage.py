"""存储池管理 API 插件"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from security.auth import AuthManager, User
from storage.zfs import zfs_manager
from dataclasses import asdict

router = APIRouter(prefix="/api/v1/storage", tags=["存储"])

auth_manager = AuthManager()


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


@router.get("/pools")
async def list_pools(current_user: User = Depends(get_current_user)):
    """列出所有 ZFS 池"""
    pools = zfs_manager.list_pools()
    return [asdict(p) for p in pools]


@router.post("/pools")
async def create_pool(name: str, vdevs: str, current_user: User = Depends(get_current_user)):
    """创建 ZFS 池"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    
    result = zfs_manager.create_pool(name, vdevs.split(","))
    return result


@router.delete("/pools/{pool_name}")
async def delete_pool(pool_name: str, current_user: User = Depends(get_current_user)):
    """删除 ZFS 池"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    
    result = zfs_manager.delete_pool(pool_name)
    return result


@router.get("/datasets")
async def list_datasets(pool: str = None, current_user: User = Depends(get_current_user)):
    """列出数据集"""
    datasets = zfs_manager.list_datasets(pool)
    return [asdict(d) for d in datasets]


@router.post("/datasets")
async def create_dataset(name: str, pool: str, current_user: User = Depends(get_current_user)):
    """创建数据集"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    
    result = zfs_manager.create_dataset(pool, name)
    return result


@router.delete("/datasets/{dataset}")
async def delete_dataset(dataset: str, current_user: User = Depends(get_current_user)):
    """删除数据集"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    
    result = zfs_manager.delete_dataset(dataset)
    return result


@router.post("/pools/{pool_name}/scrub")
async def scrub_pool(pool_name: str, current_user: User = Depends(get_current_user)):
    """启动池 scrubbing"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    
    result = zfs_manager.scrub(pool_name)
    return result
