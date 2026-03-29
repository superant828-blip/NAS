"""
存储插件 - ZFS池、数据集、快照管理
"""
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from dataclasses import asdict

from security.auth import auth_manager, User
from storage.zfs import zfs_manager, ZFSPool, ZFSDataset
from share.snapshot import snapshot_manager, ZFSSnapshot


# ==================== 路由配置 ====================

router = APIRouter(prefix="/api/v1/storage", tags=["存储"])

snapshot_router = APIRouter(prefix="/api/v1/snapshots", tags=["快照"])


# ==================== 依赖注入 ====================

def get_current_user(authorization: str = Header(None)) -> User:
    """获取当前用户 - 从Header获取"""
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


# ==================== ZFS 存储管理 ====================

@router.get("/pools")
async def list_pools(current_user: User = Depends(get_current_user)):
    """列出所有 ZFS 池"""
    pools = zfs_manager.list_pools()
    return [asdict(p) for p in pools]


@router.post("/pools")
async def create_pool(
    name: str,
    vdevs: List[str],
    layout: str = "basic",
    current_user: User = Depends(require_admin)
):
    """创建 ZFS 池"""
    result = zfs_manager.create_pool(name, vdevs, layout)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@router.get("/pools/{pool_name}")
async def get_pool(pool_name: str, current_user: User = Depends(get_current_user)):
    """获取池信息"""
    pool = zfs_manager.get_pool(pool_name)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    
    status_info = zfs_manager.get_pool_status(pool_name)
    disks = zfs_manager.get_disk_info(pool_name)
    
    return {
        "pool": asdict(pool),
        "status": status_info,
        "disks": [asdict(d) for d in disks]
    }


@router.delete("/pools/{pool_name}")
async def delete_pool(pool_name: str, force: bool = False, current_user: User = Depends(require_admin)):
    """删除 ZFS 池"""
    result = zfs_manager.destroy_pool(pool_name, force)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@router.post("/pools/{pool_name}/scrub")
async def scrub_pool(pool_name: str, current_user: User = Depends(require_admin)):
    """启动池清理"""
    result = zfs_manager.scrub_pool(pool_name)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


# ==================== 数据集管理 ====================

@router.get("/datasets")
async def list_datasets(pool: str = None, current_user: User = Depends(get_current_user)):
    """列出数据集"""
    datasets = zfs_manager.list_datasets(pool)
    return [asdict(d) for d in datasets]


@router.post("/datasets")
async def create_dataset(
    name: str,
    properties: Dict = None,
    current_user: User = Depends(get_current_user)
):
    """创建数据集"""
    result = zfs_manager.create_dataset(name, properties)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@router.delete("/datasets/{dataset}")
async def delete_dataset(
    dataset: str,
    force: bool = False,
    recursive: bool = False,
    current_user: User = Depends(get_current_user)
):
    """删除数据集"""
    result = zfs_manager.destroy_dataset(dataset, force, recursive)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


# ==================== 快照管理 ====================

@snapshot_router.get("")
async def list_snapshots(pool: str = None, dataset: str = None, current_user: User = Depends(get_current_user)):
    """列出快照"""
    snapshots = snapshot_manager.list_snapshots(pool, dataset)
    return [asdict(s) for s in snapshots]


@snapshot_router.post("")
async def create_snapshot(
    dataset: str,
    name: str,
    recursive: bool = False,
    current_user: User = Depends(get_current_user)
):
    """创建快照"""
    result = snapshot_manager.create_snapshot(dataset, name, recursive)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@snapshot_router.delete("/{snapshot}")
async def delete_snapshot(snapshot: str, recursive: bool = False, current_user: User = Depends(get_current_user)):
    """删除快照"""
    result = snapshot_manager.delete_snapshot(snapshot, recursive)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


@snapshot_router.post("/{snapshot}/rollback")
async def rollback_snapshot(snapshot: str, force: bool = False, current_user: User = Depends(get_current_user)):
    """回滚到快照"""
    result = snapshot_manager.rollback_snapshot(snapshot, force)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result