"""
智能体 API 路由
集成多智能体系统：测试、编程、调优
"""
import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time

from core.logging import logger

# 智能体模块导入
from api.agents.multi_agent.coordinator import (
    AgentCoordinator, 
    CoordinationMode, 
    get_coordinator,
    WorkerAgent
)
from api.agents.multi_agent.test_agent import TestAgent, TestType
from api.agents.multi_agent.coding_agent import CodingAgent, CodeTaskType
from api.agents.multi_agent.tuning_agent import TuningAgent, TuningTarget
from security.auth import User, auth_manager

router = APIRouter(prefix="/api/v1/agents", tags=["智能体"])


def get_current_user(authorization: str = None) -> User:
    """简单的用户认证 - 暂时返回默认用户"""
    # 暂时返回默认管理员用户
    return User(
        id=1,
        username="admin",
        email="admin@nas.local",
        password_hash="",
        role="admin",
        enabled=True
    )


# ==================== 请求/响应模型 ====================

class AgentTaskRequest(BaseModel):
    """智能体任务请求"""
    agent_type: str  # test, coding, tuning
    task: str
    input_data: Dict[str, Any] = {}
    mode: str = "parallel"  # sequential, parallel


class AgentTaskResponse(BaseModel):
    """智能体任务响应"""
    task_id: str
    status: str
    agent_type: str
    message: str


class BatchTaskRequest(BaseModel):
    """批量任务请求"""
    tasks: List[Dict[str, Any]]
    mode: str = "parallel"


class AgentStatusResponse(BaseModel):
    """智能体状态响应"""
    stats: Dict[str, Any]
    workers: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]


# ==================== 单任务接口 ====================

@router.post("/tasks", response_model=AgentTaskResponse)
async def create_agent_task(
    request: AgentTaskRequest,
    current_user = Depends(get_current_user)
):
    """
    创建智能体任务
    
    - agent_type: test(测试) / coding(编程) / tuning(调优)
    - task: 任务描述
    - input_data: 输入数据
    - mode: 执行模式 parallel/sequential
    """
    coordinator = get_coordinator()
    
    # 提交任务
    task = await coordinator.submit_task(
        agent_type=request.agent_type,
        task=request.task,
        input_data=request.input_data
    )
    
    logger.info(f"Agent task created: {task.id} ({request.agent_type})")
    
    return AgentTaskResponse(
        task_id=task.id,
        status=task.status,
        agent_type=request.agent_type,
        message=f"Task submitted successfully"
    )


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user = Depends(get_current_user)
):
    """获取任务状态"""
    coordinator = get_coordinator()
    
    task = coordinator.get_task_status(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    current_user = Depends(get_current_user)
):
    """列出任务"""
    coordinator = get_coordinator()
    
    tasks = coordinator.list_tasks(status=status, limit=limit)
    
    return {
        "tasks": tasks,
        "count": len(tasks)
    }


# ==================== 批量任务接口 ====================

@router.post("/tasks/batch")
async def create_batch_tasks(
    request: BatchTaskRequest,
    current_user = Depends(get_current_user)
):
    """批量创建任务"""
    coordinator = get_coordinator()
    
    # 转换模式
    mode = CoordinationMode.PARALLEL if request.mode == "parallel" else CoordinationMode.SEQUENTIAL
    
    # 提交批量任务
    tasks = await coordinator.submit_batch(request.tasks, mode=mode)
    
    return {
        "tasks": [t.to_dict() for t in tasks],
        "count": len(tasks),
        "mode": request.mode
    }


# ==================== 专用智能体接口 ====================

@router.post("/test/run")
async def run_test_task(
    test_type: str = "unit",
    target: str = "",
    current_user = Depends(get_current_user)
):
    """
    运行测试任务
    
    - test_type: unit/integration/api/regression/smoke
    - target: 目标文件或模块
    """
    agent = TestAgent()
    
    task = f"{test_type} test for {target}"
    input_data = {"target": target, "type": test_type}
    
    result = await agent.run(task, input_data)
    
    return result.to_dict()


@router.post("/coding/run")
async def run_coding_task(
    task_type: str = "generate",
    target: str = "",
    requirements: str = "",
    current_user = Depends(get_current_user)
):
    """
    运行编程任务
    
    - task_type: generate/refactor/fix_bug/review/optimize
    - target: 目标文件
    - requirements: 需求描述
    """
    agent = CodingAgent()
    
    task = f"{task_type} {target}"
    input_data = {
        "target": target,
        "task_type": task_type,
        "requirements": requirements.split(",") if requirements else []
    }
    
    result = await agent.run(task, input_data)
    
    return result.to_dict()


@router.post("/tuning/run")
async def run_tuning_task(
    target: str = "api",
    current_user = Depends(get_current_user)
):
    """
    运行性能调优任务
    
    - target: database/cache/api/query/config
    """
    agent = TuningAgent()
    
    task = f"optimize {target}"
    input_data = {"target": target}
    
    result = await agent.run(task, input_data)
    
    return result.to_dict()


# ==================== 协调器状态接口 ====================

@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(current_user = Depends(get_current_user)):
    """获取智能体系统状态"""
    coordinator = get_coordinator()
    
    return AgentStatusResponse(
        stats=coordinator.get_stats(),
        workers=[w.to_dict() for w in coordinator.workers.values()],
        tasks=coordinator.list_tasks(limit=20)
    )


@router.post("/workers/register")
async def register_worker(
    name: str,
    agent_type: str,
    tools: List[str],
    current_user = Depends(get_current_user)
):
    """注册工作智能体"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    
    coordinator = get_coordinator()
    
    worker = WorkerAgent(
        id=str(uuid.uuid4())[:8],
        name=name,
        agent_type=agent_type,
        tools=tools
    )
    
    coordinator.register_worker(worker)
    
    return {"success": True, "worker_id": worker.id}


@router.delete("/workers/{worker_id}")
async def unregister_worker(
    worker_id: str,
    current_user = Depends(get_current_user)
):
    """注销工作智能体"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    
    coordinator = get_coordinator()
    
    success = coordinator.unregister_worker(worker_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    return {"success": True}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user = Depends(get_current_user)
):
    """取消任务"""
    coordinator = get_coordinator()
    
    success = coordinator.cancel_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
    
    return {"success": True, "task_id": task_id}


# ==================== 流水线接口 ====================

@router.post("/pipeline/test-and-fix")
async def test_and_fix_pipeline(
    target: str,
    current_user = Depends(get_current_user)
):
    """
    测试 + 修复流水线
    
    1. 运行测试
    2. 如果失败，自动尝试修复
    3. 重新测试
    """
    coordinator = get_coordinator()
    
    # 阶段1: 测试
    test_task = await coordinator.submit_task(
        agent_type="test",
        task=f"运行测试 {target}",
        input_data={"target": target}
    )
    
    # 等待测试完成
    while test_task.status == "pending" or test_task.status == "running":
        await asyncio.sleep(0.5)
    
    # 检查结果
    if test_task.status == "completed" and test_task.result:
        # 获取测试结果
        result_data = test_task.result
        failed = result_data.get("data", {}).get("summary", {}).get("failed", 0)
        
        if failed > 0:
            # 阶段2: 修复
            fix_task = await coordinator.submit_task(
                agent_type="coding",
                task=f"修复测试失败",
                input_data={"target": target, "test_errors": result_data}
            )
            
            return {
                "phase": "fix_needed",
                "test_result": result_data,
                "fix_task_id": fix_task.id
            }
        
        return {
            "phase": "success",
            "test_result": result_data
        }
    
    return {
        "phase": "failed",
        "error": test_task.error
    }


# 导入 uuid
import uuid
# === 智能助手 API (v3.1.0+) ===

@router.post("/assistant/chat")
async def assistant_chat(request: dict):
    """智能助手对话"""
    try:
        from api.agents.assistant.smart_assistant import SmartAssistantAgent
        from api.tools.base import ToolContext
        
        agent = SmartAssistantAgent()
        context = ToolContext(user_id=1, username='user')
        
        result = await agent.run(request.get('message', ''), context)
        
        return {
            'success': result.success,
            'reply': result.data.get('message', str(result.data)) if result.data else result.error,
            'data': result.data
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@router.post("/predict/{predict_type}")
async def run_prediction(predict_type: str, request: dict = {}):
    """预测分析"""
    try:
        from api.agents.assistant.predictive_agent import PredictiveAgent
        
        agent = PredictiveAgent()
        task = request.get('task', f'{predict_type} prediction')
        
        result = await agent.run(task, {})
        
        return {
            'success': result.success,
            'data': result.data,
            'error': result.error
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@router.get("/predict/trends")
async def get_trends():
    """获取趋势分析"""
    try:
        from api.agents.assistant.predictive_agent import PredictiveAgent
        
        agent = PredictiveAgent()
        result = await agent.run('trend analysis', {})
        
        return {'success': result.success, 'data': result.data}
    except Exception as e:
        return {'success': False, 'error': str(e)}

print('✅ 智能助手路由已添加')
