# NAS-v2 基于 Claude Code 技术的优化方案

> 参考 Claude Code 源码架构进行重构 | 2026-04-01

---

## 一、优化目标

将 Claude Code 的核心设计模式应用到 NAS-v2 项目：

1. **工具系统** - 统一的工具抽象和执行框架
2. **权限引擎** - 分级权限控制
3. **任务系统** - 异步任务编排
4. **事件系统** - 解耦事件驱动
5. **Agent 集成** - AI 自动化能力

---

## 二、当前架构 vs 目标架构

### 当前架构 (main.py 79KB)
```
main.py
├── 直接路由定义
├── 内联业务逻辑
├── 简单权限检查
└── 同步执行模式
```

### 目标架构
```
api/
├── main.py              # 入口 (精简)
├── tools/               # 工具系统 NEW!
│   ├── __init__.py
│   ├── base.py          # Tool 基类
│   ├── file_tool.py     # 文件操作工具
│   ├── shell_tool.py    # Shell 执行工具
│   ├── zfs_tool.py      # ZFS 管理工具
│   ├── smb_tool.py      # SMB 共享工具
│   └── task_tool.py     # 任务工具
├── permissions/         # 权限系统 NEW!
│   ├── __init__.py
│   ├── engine.py        # 权限引擎
│   ├── rules.py         # 权限规则
│   └── context.py       # 权限上下文
├── jobs/                # 任务系统 NEW!
│   ├── __init__.py
│   ├── manager.py       # 任务管理器
│   ├── scheduler.py     # 调度器
│   └── runner.py        # 任务运行器
├── events/              # 事件系统 NEW!
│   ├── __init__.py
│   ├── dispatcher.py   # 事件分发器
│   └── handlers.py      # 事件处理器
├── agents/              # AI Agent NEW!
│   ├── __init__.py
│   ├── base.py          # Agent 基类
│   └── file_agent.py    # 文件管理 Agent
├── plugins/             # 插件系统 (扩展)
│   └── ...
├── services/            # 服务层
│   ├── cache.py
│   ├── security.py
│   └── ...
└── routes/              # 路由层
    ├── __init__.py
    ├── files.py
    ├── auth.py
    └── ...
```

---

## 三、核心模块设计

### 3.1 工具系统 (Tool System)

参考 Claude Code 的 `Tool.ts`，创建统一的工具抽象：

```python
# api/tools/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pydantic import BaseModel
from enum import Enum

class PermissionMode(str, Enum):
    AUTO = "auto"      # 自动批准
    ASK = "ask"        # 询问用户
    BYPASS = "bypass" # 绕过
    DENY = "deny"     # 拒绝

class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str = None
    metadata: Dict = {}

class ToolContext(BaseModel):
    user_id: int
    permission_mode: PermissionMode = PermissionMode.ASK
    cwd: str = "/"
    session_id: str = None

class BaseTool(ABC):
    name: str
    description: str
    input_schema: Dict
    
    @abstractmethod
    async def execute(self, input_data: Dict, context: ToolContext) -> ToolResult:
        pass
    
    def get_permission_requirements(self) -> List[str]:
        return []

# 文件工具示例
class FileReadTool(BaseTool):
    name = "file_read"
    description = "读取文件内容"
    
    async def execute(self, input_data: Dict, context: ToolContext) -> ToolResult:
        path = input_data.get("path")
        # 权限检查
        # 执行读取
        # 返回结果
        return ToolResult(success=True, data=content)
```

### 3.2 权限引擎

```python
# api/permissions/engine.py
from typing import Optional, List
from enum import Enum

class PermissionResult:
    allowed: bool
    reason: Optional[str] = None

class PermissionEngine:
    def __init__(self):
        self.rules = []
        self.dangerous_files = {
            '.gitconfig', '.bashrc', '.zshrc',
            '.mcp.json', '.claude.json', '.gitmodules'
        }
        self.dangerous_directories = {
            '.git', '.vscode', '.idea', '.claude'
        }
    
    async def check(self, tool: str, input_data: Dict, context) -> PermissionResult:
        # 1. 检查危险操作
        if self._is_dangerous(tool, input_data):
            if context.permission_mode == PermissionMode.DENY:
                return PermissionResult(allowed=False, reason="危险操作被拒绝")
        
        # 2. 检查规则匹配
        rule = self._find_matching_rule(tool, input_data)
        if rule:
            return PermissionResult(allowed=rule.allow, reason=rule.reason)
        
        # 3. 根据模式决定
        if context.permission_mode == PermissionMode.AUTO:
            return PermissionResult(allowed=True)
        elif context.permission_mode == PermissionMode.BYPASS:
            return PermissionResult(allowed=True)
        
        return PermissionResult(allowed=True)  # 需询问用户
```

### 3.3 任务系统

```python
# api/jobs/manager.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
import asyncio

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    id: str
    name: str
    status: JobStatus
    tool_name: str
    input_data: dict
    result: Any = None
    error: str = None
    created_at: float
    started_at: float = None
    completed_at: float = None

class JobManager:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.max_concurrent = 10
        self._semaphore = asyncio.Semaphore(10)
    
    async def submit(self, tool_name: str, input_data: dict) -> str:
        job = Job(
            id=generate_uuid(),
            name=f"{tool_name}_{timestamp}",
            status=JobStatus.PENDING,
            tool_name=tool_name,
            input_data=input_data,
            created_at=time.time()
        )
        self.jobs[job.id] = job
        asyncio.create_task(self._run_job(job))
        return job.id
    
    async def _run_job(self, job: Job):
        async with self._semaphore:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            try:
                tool = get_tool(job.tool_name)
                result = await tool.execute(job.input_data, context)
                job.result = result
                job.status = JobStatus.COMPLETED
            except Exception as e:
                job.error = str(e)
                job.status = JobStatus.FAILED
            finally:
                job.completed_at = time.time()
```

### 3.4 事件系统

```python
# api/events/dispatcher.py
from typing import Callable, Dict, List
from enum import Enum

class EventType(str, Enum):
    FILE_CREATED = "file.created"
    FILE_DELETED = "file.deleted"
    FILE_MODIFIED = "file.modified"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    ZFS_SNAPSHOT = "zfs.snapshot"
    SHARE_CREATED = "share.created"

class EventDispatcher:
    def __init__(self):
        self.handlers: Dict[EventType, List[Callable]] = {}
    
    def on(self, event_type: EventType, handler: Callable):
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    async def dispatch(self, event_type: EventType, data: dict):
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")

# 使用示例
dispatcher = EventDispatcher()
dispatcher.on(EventType.FILE_CREATED, lambda data: logger.info(f"File created: {data['path']}"))
```

### 3.5 AI Agent 集成

```python
# api/agents/file_agent.py
from typing import List, Optional
from tools import ToolContext, ToolResult

class FileAgent:
    """文件管理 AI Agent"""
    
    def __init__(self, tools: List[BaseTool], model: str = "claude"):
        self.tools = {t.name: t for t in tools}
        self.model = model
    
    async def execute_task(self, task: str, context: ToolContext) -> ToolResult:
        # 1. 解析任务
        plan = await self._plan_task(task)
        
        # 2. 执行工具调用
        results = []
        for step in plan["steps"]:
            tool_name = step["tool"]
            input_data = step["input"]
            
            tool = self.tools.get(tool_name)
            if not tool:
                return ToolResult(success=False, error=f"Tool {tool_name} not found")
            
            # 权限检查
            perm_result = await permission_engine.check(tool_name, input_data, context)
            if not perm_result.allowed:
                return ToolResult(success=False, error=perm_result.reason)
            
            result = await tool.execute(input_data, context)
            results.append(result)
            
            if not result.success:
                return result
        
        return ToolResult(success=True, data={"steps": results})
```

---

## 四、路由层重构

```python
# api/routes/files.py
from fastapi import APIRouter, Depends
from tools import ToolContext, get_current_user_context

router = APIRouter(prefix="/api/v1/files", tags=["files"])

@router.get("/")
async def list_files(
    path: str = "/",
    context: ToolContext = Depends(get_current_user_context)
):
    # 使用工具系统
    tool = FileReadTool()
    return await tool.execute({"path": path, "list": True}, context)

@router.post("/upload")
async def upload_file(
    file: UploadFile,
    path: str = "/",
    context: ToolContext = Depends(get_current_user_context)
):
    tool = FileWriteTool()
    return await tool.execute({
        "path": path,
        "content": await file.read(),
        "filename": file.filename
    }, context)

@router.post("/jobs")
async def create_file_job(
    operation: str,
    params: dict,
    context: ToolContext = Depends(get_current_user_context)
):
    # 提交异步任务
    job_id = await job_manager.submit(operation, params)
    return {"job_id": job_id}
```

---

## 五、实施计划

### Phase 1: 基础设施 (1-2天)
- [ ] 创建工具基类 (`api/tools/base.py`)
- [ ] 实现权限引擎 (`api/permissions/`)
- [ ] 重构 main.py 入口

### Phase 2: 核心工具 (2-3天)
- [ ] 文件操作工具 (读/写/编辑/删除)
- [ ] ZFS 管理工具
- [ ] 共享服务工具 (SMB/NFS)

### Phase 3: 任务系统 (1-2天)
- [ ] Job 管理器
- [ ] 后台任务执行
- [ ] 进度跟踪 API

### Phase 4: 事件系统 (1天)
- [ ] 事件分发器
- [ ] 关键事件钩子
- [ ] 日志集成

### Phase 5: Agent 集成 (2-3天)
- [ ] Agent 基类
- [ ] 自然语言任务解析
- [ ] 多步骤任务规划

---

## 六、优势分析

| 特性 | 当前架构 | 优化后架构 |
|------|---------|-----------|
| **可扩展性** | 困难 | 工具注册即插即用 |
| **权限控制** | 简单 if/else | 规则引擎 + 危险检测 |
| **任务管理** | 同步阻塞 | 异步 + 并发控制 |
| **代码复用** | 内联逻辑 | 工具/服务分层 |
| **AI 集成** | 无 | Agent 框架支持 |
| **可测试性** | 困难 | 单元测试工具 |

---

*优化方案完成，待实施*