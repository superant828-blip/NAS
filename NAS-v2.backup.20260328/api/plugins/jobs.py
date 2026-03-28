"""任务管理 API 插件"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from api.core.job import job_service, JobState, Job


router = APIRouter(prefix="/api/v1", tags=["jobs"])


# ==================== 依赖项 ====================
def get_current_user():
    """简化版用户获取 - 实际项目中需要完整认证"""
    # 模拟返回管理员用户
    class MockUser:
        id = 1
        username = "admin"
    return MockUser()


# ==================== 模型 ====================
class JobResponse(BaseModel):
    id: str
    description: str
    state: str
    progress: int
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class JobListResponse(BaseModel):
    total: int
    jobs: List[JobResponse]


# ==================== API 端点 ====================

@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    include_completed: bool = True,
    limit: int = 100,
    current_user = Depends(get_current_user)
):
    """
    列出所有任务
    - include_completed: 是否包含已完成的任务
    - limit: 返回任务数量限制
    """
    jobs = job_service.list(include_completed=include_completed, limit=limit)
    return {
        "total": len(jobs),
        "jobs": jobs
    }


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """
    获取任务详情
    """
    job = job_service.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "description": job.description,
        "state": job.state.value if isinstance(job.state, JobState) else job.state,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """
    取消任务
    - 只能取消 PENDING 或 RUNNING 状态的任务
    """
    job = job_service.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.state not in [JobState.PENDING, JobState.RUNNING]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel job in state: {job.state}"
        )
    
    job_service.cancel(job_id)
    return {"message": "Job cancelled successfully", "job_id": job_id}


@router.delete("/jobs/{job_id}/cleanup")
async def cleanup_job(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """
    删除任务（清理已完成的任务）
    """
    job = job_service.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_service.delete(job_id)
    return {"message": "Job deleted successfully", "job_id": job_id}