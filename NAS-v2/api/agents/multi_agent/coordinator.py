"""
多智能体协调器
参考 Claude Code Coordinator 架构设计
"""
import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional, Callable, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CoordinationMode(str, Enum):
    """协调模式"""
    SEQUENTIAL = "sequential"      # 顺序执行
    PARALLEL = "parallel"          # 并行执行
    HIERARCHICAL = "hierarchical"  # 层级协调
    BROADCAST = "broadcast"        # 广播模式


@dataclass
class AgentTask:
    """智能体任务"""
    id: str
    agent_type: str
    task: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: str = None
    started_at: float = None
    completed_at: float = None
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "task": self.task,
            "input_data": self.input_data,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "completed_at": datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None,
            "dependencies": self.dependencies
        }


@dataclass
class WorkerAgent:
    """工作智能体"""
    id: str
    name: str
    agent_type: str
    status: str = "idle"  # idle, busy, error
    current_task: str = None
    capabilities: Set[str] = field(default_factory=set)
    tools: List[str] = field(default_factory=list)
    max_concurrent: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type,
            "status": self.status,
            "current_task": self.current_task,
            "capabilities": list(self.capabilities),
            "tools": self.tools,
            "max_concurrent": self.max_concurrent
        }


class MessageChannel:
    """智能体间消息通道"""
    
    def __init__(self):
        self.subscribers: Dict[str, asyncio.Queue] = {}
        self.message_history: List[Dict[str, Any]] = []
        self.max_history = 1000
    
    def subscribe(self, agent_id: str) -> asyncio.Queue:
        """订阅消息"""
        if agent_id not in self.subscribers:
            self.subscribers[agent_id] = asyncio.Queue()
        return self.subscribers[agent_id]
    
    def unsubscribe(self, agent_id: str):
        """取消订阅"""
        if agent_id in self.subscribers:
            del self.subscribers[agent_id]
    
    async def send(self, from_agent: str, to_agent: str, message: Dict[str, Any]):
        """发送消息"""
        msg = {
            "from": from_agent,
            "to": to_agent,
            "data": message,
            "timestamp": time.time()
        }
        self.message_history.append(msg)
        
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
        
        if to_agent in self.subscribers:
            await self.subscribers[to_agent].put(msg)
    
    async def broadcast(self, from_agent: str, message: Dict[str, Any]):
        """广播消息"""
        msg = {
            "from": from_agent,
            "to": "*",
            "data": message,
            "timestamp": time.time()
        }
        self.message_history.append(msg)
        
        for queue in self.subscribers.values():
            await queue.put(msg)
    
    def get_history(self, agent_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """获取消息历史"""
        if agent_id:
            return [
                m for m in self.message_history
                if m["from"] == agent_id or m["to"] == agent_id or m["to"] == "*"
            ][-limit:]
        return self.message_history[-limit:]


class AgentCoordinator:
    """
    多智能体协调器
    
    参考 Claude Code Coordinator 架构：
    - 任务分发
    - 工作智能体管理
    - 消息通信
    - 结果聚合
    """
    
    def __init__(self, mode: CoordinationMode = CoordinationMode.SEQUENTIAL):
        self.mode = mode
        self.workers: Dict[str, WorkerAgent] = {}
        self.tasks: Dict[str, AgentTask] = {}
        self.message_channel = MessageChannel()
        self.max_concurrent_tasks = 10
        self._semaphore = asyncio.Semaphore(10)
        self._running_tasks: Dict[str, asyncio.Task] = {}
        
        # 回调函数
        self.on_task_start: Optional[Callable] = None
        self.on_task_complete: Optional[Callable] = None
        self.on_task_error: Optional[Callable] = None
    
    def register_worker(self, worker: WorkerAgent):
        """注册工作智能体"""
        self.workers[worker.id] = worker
        logger.info(f"Registered worker: {worker.name} ({worker.agent_type})")
    
    def unregister_worker(self, worker_id: str) -> bool:
        """注销工作智能体"""
        if worker_id in self.workers:
            del self.workers[worker_id]
            return True
        return False
    
    def get_available_workers(self, agent_type: str = None) -> List[WorkerAgent]:
        """获取可用智能体"""
        workers = []
        for worker in self.workers.values():
            if worker.status == "idle":
                if agent_type is None or worker.agent_type == agent_type:
                    if worker.current_task is None or worker.max_concurrent > 1:
                        workers.append(worker)
        return workers
    
    async def submit_task(
        self,
        agent_type: str,
        task: str,
        input_data: Dict[str, Any] = None,
        dependencies: List[str] = None
    ) -> AgentTask:
        """提交任务"""
        task_obj = AgentTask(
            id=str(uuid.uuid4())[:8],
            agent_type=agent_type,
            task=task,
            input_data=input_data or {},
            dependencies=dependencies or []
        )
        
        self.tasks[task_obj.id] = task_obj
        logger.info(f"Task submitted: {task_obj.id} ({agent_type})")
        
        # 自动执行
        asyncio.create_task(self._execute_task(task_obj))
        
        return task_obj
    
    async def submit_batch(
        self,
        tasks: List[Dict[str, Any]],
        mode: CoordinationMode = None
    ) -> List[AgentTask]:
        """批量提交任务"""
        mode = mode or self.mode
        
        if mode == CoordinationMode.PARALLEL:
            # 并行执行
            task_objects = []
            for t in tasks:
                task_obj = AgentTask(
                    id=str(uuid.uuid4())[:8],
                    agent_type=t.get("agent_type"),
                    task=t.get("task"),
                    input_data=t.get("input_data", {}),
                    dependencies=[]
                )
                self.tasks[task_obj.id] = task_obj
                task_objects.append(task_obj)
                asyncio.create_task(self._execute_task(task_obj))
            
            return task_objects
        
        elif mode == CoordinationMode.SEQUENTIAL:
            # 顺序执行
            task_objects = []
            for t in tasks:
                task_obj = AgentTask(
                    id=str(uuid.uuid4())[:8],
                    agent_type=t.get("agent_type"),
                    task=t.get("task"),
                    input_data=t.get("input_data", {}),
                    dependencies=[]
                )
                self.tasks[task_obj.id] = task_obj
                task_objects.append(task_obj)
                await self._execute_task(task_obj)
            
            return task_objects
        
        elif mode == CoordinationMode.HIERARCHICAL:
            # 层级协调 - 主任务分配给子任务
            return await self._execute_hierarchical(tasks)
        
        return []
    
    async def _execute_hierarchical(self, tasks: List[Dict[str, Any]]) -> List[AgentTask]:
        """层级执行"""
        # 第一阶段：并行执行独立任务
        independent_tasks = [t for t in tasks if not t.get("depends_on")]
        dependent_tasks = [t for t in tasks if t.get("depends_on")]
        
        # 执行独立任务
        results = await self.submit_batch(independent_tasks, CoordinationMode.PARALLEL)
        
        # 执行依赖任务
        for task in dependent_tasks:
            depends_on = task.get("depends_on", [])
            # 等待依赖完成
            for dep_id in depends_on:
                dep_task = self.tasks.get(dep_id)
                while dep_task and dep_task.status != "completed":
                    await asyncio.sleep(0.1)
            
            task_obj = AgentTask(
                id=str(uuid.uuid4())[:8],
                agent_type=task.get("agent_type"),
                task=task.get("task"),
                input_data=task.get("input_data", {}),
                dependencies=depends_on
            )
            self.tasks[task_obj.id] = task_obj
            await self._execute_task(task_obj)
            results.append(task_obj)
        
        return results
    
    async def _execute_task(self, task: AgentTask):
        """执行单个任务"""
        # 检查依赖
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if dep_task and dep_task.status != "completed":
                task.status = "failed"
                task.error = f"Dependency {dep_id} not completed"
                return
        
        # 触发回调
        if self.on_task_start:
            self.on_task_start(task)
        
        task.status = "running"
        task.started_at = time.time()
        
        # 获取可用智能体
        workers = self.get_available_workers(task.agent_type)
        
        if not workers:
            # 等待空闲智能体
            workers = await self._wait_for_worker(task.agent_type)
        
        if not workers:
            task.status = "failed"
            task.error = "No available worker"
            return
        
        # 分配任务
        worker = workers[0]
        worker.status = "busy"
        worker.current_task = task.id
        
        async with self._semaphore:
            try:
                # 执行任务
                result = await self._run_agent(worker, task)
                
                task.status = "completed"
                task.result = result
                task.completed_at = time.time()
                
                if self.on_task_complete:
                    self.on_task_complete(task, result)
                
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.completed_at = time.time()
                
                if self.on_task_error:
                    self.on_task_error(task, e)
                
            finally:
                worker.status = "idle"
                worker.current_task = None
    
    async def _run_agent(self, worker: WorkerAgent, task: AgentTask) -> Dict[str, Any]:
        """运行智能体"""
        # 根据智能体类型选择执行逻辑
        from ..test_agent import TestAgent
        from ..coding_agent import CodingAgent
        from ..tuning_agent import TuningAgent
        
        if task.agent_type == "test":
            agent = TestAgent()
            result = await agent.run(task.task, task.input_data)
            return result.to_dict()
        
        elif task.agent_type == "coding":
            agent = CodingAgent()
            result = await agent.run(task.task, task.input_data)
            return result.to_dict()
        
        elif task.agent_type == "tuning":
            agent = TuningAgent()
            result = await agent.run(task.task, task.input_data)
            return result.to_dict()
        
        else:
            # 通用执行
            return {
                "success": False,
                "error": f"Unknown agent type: {task.agent_type}"
            }
    
    async def _wait_for_worker(self, agent_type: str, timeout: int = 60) -> List[WorkerAgent]:
        """等待可用智能体"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            workers = self.get_available_workers(agent_type)
            if workers:
                return workers
            await asyncio.sleep(0.5)
        
        return []
    
    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def list_tasks(self, status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """列出任务"""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        tasks.sort(key=lambda x: x.started_at or 0, reverse=True)
        
        return [t.to_dict() for t in tasks[:limit]]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if task and task.status in ["pending", "running"]:
            task.status = "cancelled"
            
            # 取消正在运行的任务
            if task_id in self._running_tasks:
                self._running_tasks[task_id].cancel()
            
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "workers": len(self.workers),
            "total_tasks": len(self.tasks),
            "pending": sum(1 for t in self.tasks.values() if t.status == "pending"),
            "running": sum(1 for t in self.tasks.values() if t.status == "running"),
            "completed": sum(1 for t in self.tasks.values() if t.status == "completed"),
            "failed": sum(1 for t in self.tasks.values() if t.status == "failed"),
        }


# 全局协调器实例
_coordinator = AgentCoordinator()


def get_coordinator() -> AgentCoordinator:
    """获取协调器实例"""
    return _coordinator