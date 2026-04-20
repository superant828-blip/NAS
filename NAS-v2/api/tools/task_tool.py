"""
任务管理工具
参考 Claude Code TaskTool 设计
"""
import uuid
import time
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, asdict

from .base import BaseTool, WriteTool, ReadOnlyTool, ToolContext, ToolResult


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
    input_data: dict
    result: Any = None
    error: str = None
    progress: float = 0.0
    created_at: float = 0
    started_at: float = None
    completed_at: float = None
    
    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "status": self.status.value,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat() if self.created_at else None,
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "completed_at": datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None
        }


class JobManager:
    """
    任务管理器 - 单例模式
    
    参考 Claude Code 任务系统设计
    """
    _instance = None
    _jobs: Dict[str, Job] = {}
    _max_concurrent = 10
    _semaphore = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._jobs = {}
            import asyncio
            cls._instance._semaphore = asyncio.Semaphore(10)
        return cls._instance
    
    def create_job(
        self,
        name: str,
        tool_name: str,
        input_data: dict
    ) -> Job:
        """创建任务"""
        job = Job(
            id=str(uuid.uuid4()),
            name=name,
            status=JobStatus.PENDING,
            tool_name=tool_name,
            input_data=input_data,
            created_at=time.time()
        )
        self._jobs[job.id] = job
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """获取任务"""
        return self._jobs.get(job_id)
    
    def list_jobs(
        self,
        status: JobStatus = None,
        limit: int = 50
    ) -> List[Job]:
        """列出任务"""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # 按创建时间倒序
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        return jobs[:limit]
    
    def cancel_job(self, job_id: str) -> bool:
        """取消任务"""
        job = self._jobs.get(job_id)
        if job and job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            return True
        return False
    
    def delete_job(self, job_id: str) -> bool:
        """删除任务"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False
    
    def get_stats(self) -> dict:
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


# 全局任务管理器
_job_manager = JobManager()


class TaskCreateTool(WriteTool):
    """任务创建工具"""
    
    name = "task_create"
    description = "创建异步任务"
    
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "任务名称"},
            "tool": {"type": "string", "description": "工具名称"},
            "input": {"type": "object", "description": "工具输入数据"},
            "async": {"type": "boolean", "description": "是否异步执行", "default": True}
        },
        "required": ["name", "tool"]
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        name = input_data.get("name")
        tool_name = input_data.get("tool")
        tool_input = input_data.get("input", {})
        
        # 检查工具是否存在
        from .registry import get_tool
        tool = get_tool(tool_name)
        
        if not tool:
            return ToolResult(success=False, error=f"Tool not found: {tool_name}")
        
        # 创建任务
        job = _job_manager.create_job(
            name=name,
            tool_name=tool_name,
            input_data=tool_input
        )
        
        # 如果是异步，在后台执行
        if input_data.get("async", True):
            import asyncio
            asyncio.create_task(self._execute_job(job, context))
        
        return ToolResult(
            success=True,
            data={
                "job_id": job.id,
                "name": job.name,
                "status": job.status.value
            },
            message=f"Task created: {job.id}"
        )
    
    async def _execute_job(self, job: Job, context: ToolContext):
        """执行任务"""
        import asyncio
        
        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        
        async with _job_manager._semaphore:
            try:
                from .registry import get_tool
                tool = get_tool(job.tool_name)
                
                if tool:
                    result = await tool.call(job.input_data, context)
                    job.result = result.model_dump() if hasattr(result, 'model_dump') else result
                    job.status = JobStatus.COMPLETED if result.success else JobStatus.FAILED
                    if not result.success:
                        job.error = result.error
                else:
                    job.status = JobStatus.FAILED
                    job.error = f"Tool not found: {job.tool_name}"
                    
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
            
            finally:
                job.completed_at = time.time()
                job.progress = 1.0


class TaskListTool(ReadOnlyTool):
    """任务列表工具"""
    
    name = "task_list"
    description = "列出所有任务"
    
    input_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["pending", "running", "completed", "failed", "cancelled"]},
            "limit": {"type": "integer", "description": "返回数量", "default": 50}
        }
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        status = input_data.get("status")
        limit = input_data.get("limit", 50)
        
        status_enum = JobStatus(status) if status else None
        
        jobs = _job_manager.list_jobs(status=status_enum, limit=limit)
        
        return ToolResult(
            success=True,
            data={
                "jobs": [job.to_dict() for job in jobs],
                "count": len(jobs),
                "stats": _job_manager.get_stats()
            }
        )


class TaskStatusTool(ReadOnlyTool):
    """任务状态工具"""
    
    name = "task_status"
    description = "获取任务状态"
    
    input_schema = {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务ID"}
        },
        "required": ["job_id"]
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        job_id = input_data.get("job_id")
        
        job = _job_manager.get_job(job_id)
        
        if not job:
            return ToolResult(success=False, error=f"Job not found: {job_id}")
        
        return ToolResult(
            success=True,
            data=job.to_dict()
        )