"""
权限引擎
参考 Claude Code 权限系统设计

核心功能：
- 危险操作检测
- 路径访问控制
- 命令安全检查
- 规则引擎
"""
from typing import Dict, Any, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
import re


class PermissionMode(str, Enum):
    """权限模式"""
    AUTO = "auto"       # 自动批准
    ASK = "ask"         # 询问用户
    BYPASS = "bypass"  # 绕过检查
    DENY = "deny"       # 全部拒绝


@dataclass
class PermissionResult:
    """权限检查结果"""
    allowed: bool
    reason: Optional[str] = None
    requires_approval: bool = False
    rule_id: Optional[str] = None


@dataclass
class PermissionRule:
    """权限规则"""
    id: str
    name: str
    pattern: str  # 正则匹配模式
    tool: Optional[str] = None  # 适用工具
    allow: bool = True
    reason: str = ""
    priority: int = 0


class PermissionEngine:
    """
    权限引擎
    
    参考 Claude Code 的权限系统设计：
    1. 危险操作检测
    2. 规则匹配
    3. 路径访问控制
    4. 管理员绕过
    """
    
    # 危险文件黑名单
    DANGEROUS_FILES = {
        '.gitconfig', '.bashrc', '.bash_profile',
        '.zshrc', '.zprofile', '.profile',
        '.ripgreprc', '.mcp.json', '.claude.json',
        '.gitmodules', 'id_rsa', 'id_ed25519',
        'authorized_keys', '.netrc', '.aws/credentials'
    }
    
    # 危险目录黑名单
    DANGEROUS_DIRECTORIES = {
        '.git', '.vscode', '.idea', '.claude',
        'node_modules', '__pycache__', '.venv',
        'venv', '.env', 'etc', 'sys', 'proc',
        'boot', 'dev', 'run', 'snap'
    }
    
    # 危险命令模式
    DANGEROUS_PATTERNS = [
        r'rm\s+-rf\s+/',
        r'dd\s+if=',
        r':\(\)\{',
        r'curl\s*\|\s*sh',
        r'wget\s*\|\s*sh',
        r'mkfs\.',
        r'>\s*/dev/sd',
        r'chmod\s+-R\s+777\s+/',
        r'chown\s+-R',
    ]
    
    # 只读工具
    READ_ONLY_TOOLS = {
        'file_list', 'file_read', 'zfs_list', 'task_list',
        'task_status', 'web_fetch', 'web_search'
    }
    
    # 写操作工具
    WRITE_TOOLS = {
        'file_write', 'file_edit', 'file_delete',
        'shell', 'zfs_snapshot', 'task_create'
    }
    
    def __init__(self):
        self.rules: List[PermissionRule] = []
        self._load_default_rules()
    
    def _load_default_rules(self):
        """加载默认规则"""
        # 默认允许规则
        self.rules = [
            PermissionRule(
                id="allow_read_nas",
                name="允许读取 NAS 数据",
                pattern=r"^/nas-pool/.*",
                tool=None,
                allow=True,
                reason="NAS 数据目录",
                priority=10
            ),
            PermissionRule(
                id="allow_uploads",
                name="允许写入上传目录",
                pattern=r"^/nas-pool/data/uploads/.*",
                tool="file_write",
                allow=True,
                reason="上传目录",
                priority=20
            ),
            PermissionRule(
                id="deny_system",
                name="拒绝系统目录",
                pattern=r"^(/etc|/sys|/proc|/boot)",
                tool=None,
                allow=False,
                reason="系统目录禁止访问",
                priority=100
            )
        ]
        
        # 按优先级排序
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    async def check(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        context: "PermissionContext"
    ) -> PermissionResult:
        """
        权限检查主入口
        """
        # 1. 管理员绕过
        if context.is_admin:
            return PermissionResult(
                allowed=True,
                reason="Admin bypass"
            )
        
        # 2. 权限模式检查
        if context.permission_mode == PermissionMode.BYPASS:
            return PermissionResult(allowed=True, reason="Bypass mode")
        
        if context.permission_mode == PermissionMode.DENY:
            return PermissionResult(allowed=False, reason="Den y mode")
        
        # 3. 只读工具自动放行
        if tool_name in self.READ_ONLY_TOOLS:
            return PermissionResult(allowed=True, reason="Read-only tool")
        
        # 4. 危险操作检测
        danger_result = self._check_dangerous_operation(tool_name, input_data)
        if not danger_result.allowed:
            return danger_result
        
        # 5. 路径检查
        path = input_data.get("path") or input_data.get("command", "")
        if path:
            path_result = self._check_path(path, tool_name)
            if not path_result.allowed:
                return path_result
        
        # 6. 规则匹配
        rule_result = self._match_rules(tool_name, input_data)
        if rule_result:
            return rule_result
        
        # 7. 写操作需要确认
        if tool_name in self.WRITE_TOOLS:
            if context.permission_mode == PermissionMode.ASK:
                return PermissionResult(
                    allowed=True,
                    requires_approval=True,
                    reason=f"Write operation requires approval"
                )
        
        return PermissionResult(allowed=True)
    
    def _check_dangerous_operation(
        self,
        tool_name: str,
        input_data: Dict[str, Any]
    ) -> PermissionResult:
        """危险操作检测"""
        command = input_data.get("command", "")
        
        # 检查危险命令模式
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return PermissionResult(
                    allowed=False,
                    reason=f"Dangerous command pattern detected: {pattern}"
                )
        
        # 检查危险文件操作
        if tool_name in ['file_read', 'file_write', 'file_edit', 'file_delete']:
            path = input_data.get("path", "")
            
            # 检查危险文件
            for danger_file in self.DANGEROUS_FILES:
                if path.endswith(danger_file):
                    return PermissionResult(
                        allowed=False,
                        reason=f"Access to dangerous file denied: {danger_file}"
                    )
        
        return PermissionResult(allowed=True)
    
    def _check_path(self, path: str, tool_name: str) -> PermissionResult:
        """路径访问检查"""
        # 检查危险目录
        for danger_dir in self.DANGEROUS_DIRECTORIES:
            if f"/{danger_dir}" in path or path.startswith(danger_dir + "/"):
                return PermissionResult(
                    allowed=False,
                    reason=f"Access to dangerous directory denied: {danger_dir}"
                )
        
        # 路径遍历检查
        if ".." in path:
            # 检查是否逃离允许目录
            if not any(path.startswith(allowed) for allowed in context.allowed_paths):
                return PermissionResult(
                    allowed=False,
                    reason="Path traversal detected"
                )
        
        return PermissionResult(allowed=True)
    
    def _match_rules(
        self,
        tool_name: str,
        input_data: Dict[str, Any]
    ) -> Optional[PermissionResult]:
        """规则匹配"""
        path = input_data.get("path", "")
        
        for rule in self.rules:
            # 工具过滤
            if rule.tool and rule.tool != tool_name:
                continue
            
            # 路径匹配
            if rule.pattern:
                try:
                    if re.match(rule.pattern, path):
                        return PermissionResult(
                            allowed=rule.allow,
                            reason=rule.reason,
                            rule_id=rule.id
                        )
                except re.error:
                    pass
        
        return None
    
    def add_rule(self, rule: PermissionRule):
        """添加规则"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_id: str) -> bool:
        """移除规则"""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                del self.rules[i]
                return True
        return False
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """获取所有规则"""
        return [
            {
                "id": r.id,
                "name": r.name,
                "pattern": r.pattern,
                "tool": r.tool,
                "allow": r.allow,
                "reason": r.reason,
                "priority": r.priority
            }
            for r in self.rules
        ]


# 全局权限引擎实例
permission_engine = PermissionEngine()


# 导入需要
from .context import PermissionContext