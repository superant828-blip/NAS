"""
Agent 基类
参考 Claude Code AgentTool 设计
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid


class AgentCapability(str, Enum):
    """Agent 能力"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    SHELL_EXEC = "shell_exec"
    WEB_ACCESS = "web_access"
    ZFS_MANAGE = "zfs_manage"
    USER_MANAGE = "user_manage"
    TASK_CREATE = "task_create"


@dataclass
class AgentDefinition:
    """Agent 定义"""
    name: str
    description: str
    capabilities: Set[AgentCapability]
    tools: List[str]  # 允许使用的工具名
    max_turns: int = 100
    model: str = "claude-sonnet"
    permission_mode: str = "bubble"  # bubble: 继承父级权限
    source: str = "built-in"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "tools": self.tools,
            "max_turns": self.max_turns,
            "model": self.model,
            "source": self.source
        }


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    total_turns: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "steps": self.steps,
            "tools_used": self.tools_used,
            "total_turns": self.total_turns
        }


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_context: Any = None
    allowed_tools: Set[str] = field(default_factory=set)
    max_turns: int = 100
    current_turn: int = 0


class AgentBase(ABC):
    """
    Agent 抽象基类
    
    参考 Claude Code AgentTool 设计
    """
    
    definition: AgentDefinition
    
    def __init__(self, definition: AgentDefinition = None):
        if definition:
            self.definition = definition
        self._setup_default_definition()
    
    def _setup_default_definition(self):
        """设置默认定义"""
        if not hasattr(self, 'definition') or not self.definition:
            self.definition = AgentDefinition(
                name=self.__class__.__name__,
                description="Base agent",
                capabilities=set(),
                tools=[]
            )
    
    @abstractmethod
    async def run(self, task: str, context: AgentContext) -> AgentResult:
        """
        执行任务
        
        Args:
            task: 任务描述
            context: 执行上下文
            
        Returns:
            AgentResult: 执行结果
        """
        pass
    
    async def plan(self, task: str) -> List[Dict[str, Any]]:
        """
        任务规划
        
        将自然语言任务分解为工具调用步骤
        
        Returns:
            步骤列表，每步包含 tool_name 和 input_data
        """
        # 默认实现：简单解析
        steps = []
        
        # 简单的关键词匹配
        task_lower = task.lower()
        
        if "list" in task_lower or "show" in task_lower or "ls" in task_lower:
            # 提取路径
            path = "/"
            for word in task.split():
                if word.startswith("/"):
                    path = word
                    break
            
            steps.append({
                "tool": "file_list",
                "input": {"path": path}
            })
        
        elif "read" in task_lower or "cat" in task_lower:
            path = None
            for word in task.split():
                if word.startswith("/") or "." in word:
                    path = word
                    break
            
            if path:
                steps.append({
                    "tool": "file_read",
                    "input": {"path": path}
                })
        
        elif "write" in task_lower or "create" in task_lower:
            # 需要更复杂的解析
            steps.append({
                "tool": "file_write",
                "input": {"path": "/tmp/placeholder", "content": "..."}
            })
        
        elif "zfs" in task_lower or "pool" in task_lower:
            steps.append({
                "tool": "zfs_list",
                "input": {}
            })
        
        return steps
    
    async def execute_step(
        self,
        step: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """执行单个步骤"""
        from ..tools import get_tool, ToolContext
        
        tool_name = step.get("tool")
        tool_input = step.get("input", {})
        
        # 检查工具权限
        if context.allowed_tools and tool_name not in context.allowed_tools:
            return {
                "success": False,
                "error": f"Tool {tool_name} not allowed"
            }
        
        # 获取工具
        tool = get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool not found: {tool_name}"
            }
        
        # 创建工具上下文
        tool_context = ToolContext(
            user_id=context.parent_context.user_id if context.parent_context else 0,
            username=context.parent_context.username if context.parent_context else "agent"
        )
        
        # 执行
        result = await tool.call(tool_input, tool_context)
        
        return result.model_dump() if hasattr(result, 'model_dump') else result


# 内置 Agent 定义
BUILT_IN_AGENTS = {
    "file-manager": AgentDefinition(
        name="file-manager",
        description="文件管理 Agent - 读取、编辑、创建文件",
        capabilities={AgentCapability.FILE_READ, AgentCapability.FILE_WRITE},
        tools=["file_list", "file_read", "file_write", "file_edit"],
        max_turns=50,
        model="claude-sonnet"
    ),
    "system-admin": AgentDefinition(
        name="system-admin",
        description="系统管理 Agent - Shell 命令和 ZFS 管理",
        capabilities={
            AgentCapability.SHELL_EXEC,
            AgentCapability.ZFS_MANAGE
        },
        tools=["shell", "zfs_list", "zfs_snapshot"],
        max_turns=30,
        model="claude-sonnet"
    ),
    "task-runner": AgentDefinition(
        name="task-runner",
        description="任务执行 Agent - 异步任务管理",
        capabilities={AgentCapability.TASK_CREATE},
        tools=["task_create", "task_list", "task_status"],
        max_turns=20,
        model="claude-sonnet"
    )
}