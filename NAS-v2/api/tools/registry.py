"""
工具注册表
参考 Claude Code 工具系统设计
"""
from typing import Dict, List, Optional, Type, Any
from .base import BaseTool, ToolResult, ToolContext
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表 - 单一实例管理所有工具
    """
    _instance = None
    _tools: Dict[str, BaseTool] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        if not tool.name:
            raise ValueError(f"Tool must have a name: {tool}")
        
        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")
        
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, tool_name: str) -> bool:
        """注销工具"""
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")
            return True
        return False
    
    def get(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "version": tool.version,
                "is_enabled": tool.is_enabled,
                "is_dangerous": tool.is_dangerous,
                "danger_level": tool.danger_level,
                "is_read_only": tool.is_read_only()
            }
            for tool in self._tools.values()
        ]
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())
    
    def find_tools(self, query: str) -> List[BaseTool]:
        """搜索工具"""
        query = query.lower()
        results = []
        
        for tool in self._tools.values():
            if query in tool.name.lower() or query in tool.description.lower():
                results.append(tool)
        
        return results
    
    def execute_tool(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """执行工具（同步包装）"""
        import asyncio
        
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}"
            )
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(tool.call(input_data, context))
    
    def get_read_only_tools(self) -> List[BaseTool]:
        """获取所有只读工具"""
        return [t for t in self._tools.values() if t.is_read_only()]
    
    def get_write_tools(self) -> List[BaseTool]:
        """获取所有写操作工具"""
        return [t for t in self._tools.values() if not t.is_read_only()]
    
    def get_dangerous_tools(self) -> List[BaseTool]:
        """获取所有危险工具"""
        return [t for t in self._tools.values() if t.is_dangerous]


# 全局注册表实例
_registry = ToolRegistry()


def register_tool(tool: BaseTool) -> None:
    """注册工具快捷函数"""
    _registry.register(tool)


def get_tool(tool_name: str) -> Optional[BaseTool]:
    """获取工具快捷函数"""
    return _registry.get(tool_name)


def list_tools() -> List[Dict[str, Any]]:
    """列出所有工具快捷函数"""
    return _registry.list_tools()


def execute_tool(
    tool_name: str,
    input_data: Dict[str, Any],
    context: ToolContext
) -> ToolResult:
    """执行工具快捷函数"""
    return _registry.execute_tool(tool_name, input_data, context)


def initialize_tools() -> None:
    """初始化所有内置工具"""
    from .file_tool import (
        FileListTool,
        FileReadTool,
        FileWriteTool,
        FileEditTool,
        FileDeleteTool
    )
    from .shell_tool import ShellTool
    from .zfs_tool import ZFSListTool, ZFSSnapshotTool
    from .task_tool import TaskCreateTool, TaskListTool, TaskStatusTool
    
    # 注册文件工具
    register_tool(FileListTool())
    register_tool(FileReadTool())
    register_tool(FileWriteTool())
    register_tool(FileEditTool())
    register_tool(FileDeleteTool())
    
    # 注册 Shell 工具
    register_tool(ShellTool())
    
    # 注册 ZFS 工具
    register_tool(ZFSListTool())
    register_tool(ZFSSnapshotTool())
    
    # 注册任务工具
    register_tool(TaskCreateTool())
    register_tool(TaskListTool())
    register_tool(TaskStatusTool())
    
    logger.info(f"Initialized {len(_registry.get_tool_names())} tools")


# 自动初始化
initialize_tools()