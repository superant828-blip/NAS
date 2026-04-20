"""任务系统 - 处理长时间运行的操作"""
import uuid
from enum import Enum
from typing import Dict, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
import threading
import asyncio


class JobState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class Job:
    id: str
    description: str
    state: JobState
    progress: int  # 0-100
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None


class JobService:
    """任务服务"""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
    
    def create_job(self, description: str) -> Job:
        """创建新任务"""
        with self._lock:
            job = Job(
                id=str(uuid.uuid4())[:8],
                description=description,
                state=JobState.PENDING,
                progress=0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self._jobs[job.id] = job
            return job
    
    def update_progress(self, job_id: str, progress: int, state: JobState = None):
        """更新任务进度"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].progress = min(100, max(0, progress))
                self._jobs[job_id].updated_at = datetime.now()
                if state:
                    self._jobs[job_id].state = state
    
    def set_running(self, job_id: str):
        """设置任务为运行中"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].state = JobState.RUNNING
                self._jobs[job_id].updated_at = datetime.now()
    
    def complete(self, job_id: str, result: Any):
        """完成任务"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].result = result
                self._jobs[job_id].state = JobState.SUCCESS
                self._jobs[job_id].progress = 100
                self._jobs[job_id].updated_at = datetime.now()
    
    def fail(self, job_id: str, error: str):
        """标记任务失败"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].error = error
                self._jobs[job_id].state = JobState.FAILED
                self._jobs[job_id].updated_at = datetime.now()
    
    def cancel(self, job_id: str):
        """取消任务"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].state = JobState.CANCELLED
                self._jobs[job_id].updated_at = datetime.now()
    
    def get(self, job_id: str) -> Optional[Job]:
        """获取任务"""
        return self._jobs.get(job_id)
    
    def list(self, include_completed: bool = True, limit: int = 100) -> list:
        """列出任务"""
        jobs = list(self._jobs.values())
        if not include_completed:
            jobs = [j for j in jobs if j.state not in [JobState.SUCCESS, JobState.FAILED, JobState.CANCELLED]]
        # 按创建时间倒序
        jobs.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        return [asdict(j) for j in jobs[:limit]]
    
    def delete(self, job_id: str):
        """删除任务"""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
    
    def run_async(self, job_id: str, func: Callable, *args, **kwargs):
        """异步运行任务"""
        def _run():
            try:
                self.set_running(job_id)
                result = func(*args, **kwargs)
                self.complete(job_id, result)
            except Exception as e:
                self.fail(job_id, str(e))
        
        thread = threading.Thread(target=_run)
        thread.daemon = True
        thread.start()
        return thread


# 全局实例
job_service = JobService()