"""
照片管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query, Form
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/photos", tags=["照片管理"])


@router.get("/")
async def list_photos(
    album_id: Optional[int] = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
    user_id: int = Depends(lambda: 1)
):
    """获取照片列表"""
    pass


@router.post("/")
async def upload_photo(
    file: UploadFile = FastAPIFile(...),
    album_id: Optional[int] = None,
    user_id: int = Depends(lambda: 1)
):
    """上传照片"""
    pass


@router.get("/{photo_id}")
async def get_photo(photo_id: int, user_id: int = Depends(lambda: 1)):
    """获取照片详情"""
    pass


@router.get("/{photo_id}/thumbnail")
async def get_thumbnail(photo_id: int, size: str = "medium"):
    """获取照片缩略图"""
    pass


@router.delete("/{photo_id}")
async def delete_photo(photo_id: int, user_id: int = Depends(lambda: 1)):
    """删除照片"""
    pass


# 相册管理
@router.get("/albums")
async def list_albums(user_id: int = Depends(lambda: 1)):
    """获取相册列表"""
    pass


@router.post("/albums")
async def create_album(
    name: str,
    description: Optional[str] = None,
    user_id: int = Depends(lambda: 1)
):
    """创建相册"""
    pass


@router.delete("/albums/{album_id}")
async def delete_album(album_id: int, user_id: int = Depends(lambda: 1)):
    """删除相册"""
    pass