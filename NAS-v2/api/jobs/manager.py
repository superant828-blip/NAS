"""
任务管理器
参考 Claude Code TaskTool 设计
"""
import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, asdict, field
from datetime import datetime


class JobStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """任务数据类"""
    id: str
    name: str
    status: JobStatus
    tool_name: str
    input_data: Dict[str, Any]
    result: Any = None
    error: str = None
    progress: float = 0.0
    logs: List[str] = field(default_factory=list)
    created_at: float = 0
    started_at: float = None
    completed_at: float = None
    user_id: int = None
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = datetime.fromtimestamp(self.created_at).isoformat() if self.created_at else None
        data["started_at"] = datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None
        data["completed_at"] = datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None
        return data


class JobManager:
    """
    任务管理器
    
    功能：
    - 任务创建/取消/删除
    - 并发控制
    - 进度跟踪
    - 日志记录
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._jobs = {}
            cls._instance._semaphore = asyncio.Semaphore(10)
            cls._instance._running_tasks = {}
        return cls._instance
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._semaphore: asyncio.Semaphore = None
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    def create_job(
        self,
        name: str,
        tool_name: str,
        input_data: Dict[str, Any],
        user_id: int = None
    ) -> Job:
        """创建任务"""
        job = Job(
            id=str(uuid.uuid4())[:8],
            name=name,
            status=JobStatus.PENDING,
            tool_name=tool_name,
            input_data=input_data,
            created_at=time.time(),
            user_id=user_id
        )
        self._jobs[job.id] = job
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """获取任务"""
        return self._jobs.get(job_id)
    
    def list_jobs(
        self,
        status: JobStatus = None,
        user_id: int = None,
        limit: int = 50
    ) -> List[Job]:
        """列出任务"""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        if user_id:
            jobs = [j for j in jobs if j.user_id == user_id]
        
        # 按创建时间倒序
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        return jobs[:limit]
    
    def cancel_job(self, job_id: str) -> bool:
        """取消任务"""
        job = self._jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            
            # 取消正在运行的任务
            if job_id in self._running_tasks:
                self._running_tasks[job_id].cancel()
            
            return True
        
        return False
    
    def delete_job(self, job_id: str) -> bool:
        """删除任务"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False
    
    async def run_job(
        self,
        job: Job,
        tool_executor: Callable[[Dict[str, Any], Any], Awaitable[Any]]
    ) -> Job:
        """运行任务"""
        async with self._semaphore:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            
            try:
                # 执行工具
                result = await tool_executor(job.input_data, None)
                job.result = result
                job.status = JobStatus.COMPLETED if result.get("success", False) else JobStatus.FAILED
                job.progress = 1.0
                
                if not result.get("success", False):
                    job.error = result.get("error", "Unknown error")
                    
            except asyncio.CancelledError:
                job.status = JobStatus.CANCELLED
                job.error = "Task cancelled"
                
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
                
            finally:
                job.completed_at = time.time()
                
            return job
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        stats = {
            "total": len(self._jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for job in self._jobs.values():
            stats[job.status.value] += 1
        
        return stats
    
    def add_log(self, job_id: str, message: str):
        """添加日志"""
        job = self._jobs.get(job_id)
        if job:
            timestamp = datetime.now().strftime("%H:%M:%S")
            job.logs.append(f"[{timestamp}] {message}")
    
    def clear_completed(self, older_than_hours: int = 24):
        """清理已完成任务"""
        cutoff = time.time() - (older_than_hours * 3600)
        to_delete = []
        
        for job_id, job in self._jobs.items():
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                if job.completed_at and job.completed_at < cutoff:
                    to_delete.append(job_id)
        
        for job_id in to_delete:
            del self._jobs[job_id]
        
        return len(to_delete)


# 全局实例
_job_manager = JobManager()


def get_job_manager() -> JobManager:
    """获取任务管理器实例"""
    return _job_manager


def create_job(name: str, tool_name: str, input_data: Dict, user_id: int = None) -> Job:
    """创建任务快捷函数"""
    return _job_manager.create_job(name, tool_name, input_data, user_id)