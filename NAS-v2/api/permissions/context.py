"""
权限上下文
"""
from typing import Set, Optional
from dataclasses import dataclass, field
from .engine import PermissionMode


@dataclass
class PermissionContext:
    """权限执行上下文"""
    user_id: int
    username: str = "anonymous"
    permission_mode: PermissionMode = PermissionMode.ASK
    is_admin: bool = False
    allowed_paths: Set[str] = field(default_factory=lambda: {"/"})
    denied_paths: Set[str] = field(default_factory=set)
    session_id: str = None
    
    # 资源限制
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    max_request_size: int = 50 * 1024 * 1024  # 50MB
    
    # 速率限制
    rate_limit_per_minute: int = 60


def get_permission_context(
    user_id: int,
    username: str = "anonymous",
    is_admin: bool = False,
    permission_mode: PermissionMode = PermissionMode.ASK
) -> PermissionContext:
    """创建权限上下文"""
    return PermissionContext(
        user_id=user_id,
        username=username,
        is_admin=is_admin,
        permission_mode=permission_mode,
        allowed_paths={"/nas-pool/data"} if not is_admin else {"/"}
    )