"""
工具系统基类
参考 Claude Code 的 Tool.ts 设计
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid


class PermissionMode(str, Enum):
    """权限模式 - 参考 Claude Code"""
    AUTO = "auto"       # 自动批准安全操作
    ASK = "ask"         # 询问用户
    BYPASS = "bypass"   # 管理员绕过
    DENY = "deny"       # 拒绝


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # 进度信息
    progress: Optional[float] = None
    message: Optional[str] = None
    
    # 耗时统计
    duration_ms: Optional[int] = None
    
    class Config:
        arbitrary_types_allowed = True


class ToolContext(BaseModel):
    """工具执行上下文"""
    user_id: int
    username: str = "anonymous"
    permission_mode: PermissionMode = PermissionMode.ASK
    cwd: str = "/"
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # 权限信息
    is_admin: bool = False
    allowed_paths: Set[str] = Field(default_factory=lambda: {"/"})
    
    # MCP 上下文
    mcp_servers: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class ToolInputSchema(BaseModel):
    """工具输入 Schema 定义"""
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class BaseTool(ABC):
    """
    工具抽象基类
    
    参考 Claude Code 的 Tool.ts 设计
    """
    
    # 工具元数据
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    
    # 输入/输出 Schema
    input_schema: ToolInputSchema = None
    output_schema: Dict[str, Any] = {}
    
    # 能力标志
    is_enabled: bool = True
    is_concurrency_safe: bool = True
    should_defer: bool = False  # 是否延迟执行
    
    # 权限要求
    required_permissions: Set[str] = set()
    
    # 危险操作标志
    is_dangerous: bool = False
    danger_level: int = 0  # 0-5, 5 最危险
    
    def __init__(self):
        if self.input_schema is None:
            self.input_schema = ToolInputSchema()
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        """
        执行工具
        
        Args:
            input_data: 工具输入数据
            context: 执行上下文
            
        Returns:
            ToolResult: 执行结果
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证输入数据
        
        Args:
            input_data: 待验证的输入
            
        Returns:
            (是否有效, 错误消息)
        """
        if not self.input_schema:
            return True, None
            
        # 检查必填字段
        for field in self.input_schema.required:
            if field not in input_data:
                return False, f"Missing required field: {field}"
        
        return True, None
    
    def get_permission_requirements(self) -> Set[str]:
        """获取权限要求"""
        return self.required_permissions
    
    def is_read_only(self) -> bool:
        """判断是否为只读操作"""
        return False
    
    def get_search_hint(self) -> str:
        """获取搜索提示"""
        return self.description
    
    def user_facing_name(self) -> str:
        """用户友好的名称"""
        return self.name.replace('_', ' ').title()
    
    async def call(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        """
        工具调用入口 - 包含权限检查和错误处理
        """
        import time
        start_time = time.time()
        
        try:
            # 1. 检查是否启用
            if not self.is_enabled:
                return ToolResult(
                    success=False,
                    error=f"Tool '{self.name}' is disabled"
                )
            
            # 2. 输入验证
            valid, error_msg = self.validate_input(input_data)
            if not valid:
                return ToolResult(
                    success=False,
                    error=f"Validation error: {error_msg}"
                )
            
            # 3. 执行工具
            result = await self.execute(input_data, context)
            
            # 4. 记录耗时
            result.duration_ms = int((time.time() - start_time) * 1000)
            
            return result
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000)
            )


class ReadOnlyTool(BaseTool):
    """只读工具基类"""
    
    def is_read_only(self) -> bool:
        return True
    
    def get_permission_requirements(self) -> Set[str]:
        return {"read"}


class WriteTool(BaseTool):
    """写操作工具基类"""
    
    def is_read_only(self) -> bool:
        return False
    
    def get_permission_requirements(self) -> Set[str]:
        return {"write"}


class DangerousTool(BaseTool):
    """危险操作工具基类"""
    
    def __init__(self):
        super().__init__()
        self.is_dangerous = True
        self.danger_level = 3
    
    def get_permission_requirements(self) -> Set[str]:
        return {"write", "dangerous"}