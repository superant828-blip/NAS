"""
NAS-v2 工具系统
基于 Claude Code 架构设计

核心组件：
- BaseTool: 工具抽象基类
- ToolContext: 工具执行上下文
- ToolResult: 工具执行结果
- ToolRegistry: 工具注册表
"""
import logging

logger = logging.getLogger(__name__)

from .base import BaseTool, ToolContext, ToolResult, PermissionMode
from .file_tool import FileReadTool, FileWriteTool, FileEditTool, FileDeleteTool, FileListTool
from .shell_tool import ShellTool
from .zfs_tool import ZFSListTool, ZFSSnapshotTool
from .task_tool import TaskCreateTool, TaskListTool, TaskStatusTool
from .registry import ToolRegistry, get_tool, register_tool, list_tools

__all__ = [
    'BaseTool',
    'ToolContext', 
    'ToolResult',
    'PermissionMode',
    'FileReadTool',
    'FileWriteTool', 
    'FileEditTool',
    'FileDeleteTool',
    'FileListTool',
    'ShellTool',
    'ZFSListTool',
    'ZFSSnapshotTool',
    'TaskCreateTool',
    'TaskListTool',
    'TaskStatusTool',
    'ToolRegistry',
    'get_tool',
    'register_tool',
    'list_tools',
    'initialize_tools'
]


def initialize_tools() -> None:
    """初始化所有内置工具"""
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
    
    logger.info(f"Initialized {len(list_tools())} tools")