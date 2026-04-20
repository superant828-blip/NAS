"""
权限系统
参考 Claude Code 权限引擎设计
"""
from .engine import PermissionEngine, PermissionResult, PermissionMode
from .context import PermissionContext, get_permission_context

__all__ = [
    'PermissionEngine',
    'PermissionResult', 
    'PermissionMode',
    'PermissionContext',
    'get_permission_context'
]