"""
分享功能路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/shares", tags=["分享功能"])


class ShareCreateRequest(BaseModel):
    file_ids: list[int]
    password: Optional[str] = None
    expire_days: int = 7
    description: Optional[str] = None


class ShareLinkRequest(BaseModel):
    file_id: int
    password: Optional[str] = None
    expire_days: int = 7


@router.post("/")
async def create_share(
    request: ShareCreateRequest,
    user_id: int = Depends(lambda: 1)
):
    """创建分享"""
    pass


@router.get("/")
async def list_shares(user_id: int = Depends(lambda: 1)):
    """获取分享列表"""
    pass


@router.get("/{share_id}")
async def get_share(share_id: int, user_id: int = Depends(lambda: 1)):
    """获取分享详情"""
    pass


@router.delete("/{share_id}")
async def delete_share(share_id: int, user_id: int = Depends(lambda: 1)):
    """删除分享"""
    pass


# 公开分享链接
@router.get("/links")
async def list_share_links(user_id: int = Depends(lambda: 1)):
    """获取分享链接列表"""
    pass


@router.post("/links")
async def create_share_link(
    request: ShareLinkRequest,
    user_id: int = Depends(lambda: 1)
):
    """创建分享链接"""
    pass


# 公开访问
@router.get("/share/{token}")
async def access_share(
    token: str,
    password: Optional[str] = None
):
    """通过Token访问分享"""
    pass