"""
Shell 命令执行工具
参考 Claude Code BashTool 安全架构设计
"""
import asyncio
import subprocess
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base import BaseTool, ToolContext, ToolResult, DangerousTool


# 危险命令黑名单
BLOCKED_COMMANDS = {
    'rm -rf /', 'dd if=/dev/zero', ':(){:|:&};:',
    'curl | sh', 'wget | sh', 'chmod -R 777 /',
    'mkfs', 'dd if=/dev/urandom', '> /dev/sda'
}

# 只读命令（可并发执行）
READ_COMMANDS = {
    'ls', 'dir', 'pwd', 'cat', 'head', 'tail', 'less', 'more',
    'grep', 'find', 'which', 'whereis', 'stat', 'file', 'wc',
    'du', 'df', 'tree', 'sort', 'uniq', 'cut', 'tr', 'jq'
}

# 需要管理员权限的命令
ADMIN_COMMANDS = {
    'rm', 'rmdir', 'mv', 'cp', 'chmod', 'chown', 'chgrp',
    'mount', 'umount', 'fdisk', 'mkfs', 'dd'
}


class ShellTool(DangerousTool):
    """
    Shell 命令执行工具
    
    参考 Claude Code BashTool 实现，包含：
    - 命令安全检查
    - 路径验证
    - 权限控制
    - 输出限制
    """
    
    name = "shell"
    description = "执行 Shell 命令"
    
    def __init__(self):
        super().__init__()
        self.danger_level = 5  # 最高危险级别
    
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令"},
            "cwd": {"type": "string", "description": "工作目录"},
            "timeout": {"type": "integer", "description": "超时时间(秒)", "default": 30},
            "env": {"type": "object", "description": "环境变量"}
        },
        "required": ["command"]
    }
    
    MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        command = input_data.get("command", "")
        cwd = input_data.get("cwd", context.cwd)
        timeout = input_data.get("timeout", 30)
        env = input_data.get("env", {})
        
        # 1. 安全检查
        security_check = self._check_command_security(command)
        if not security_check["allowed"]:
            return ToolResult(
                success=False,
                error=f"Security check failed: {security_check['reason']}"
            )
        
        # 2. 路径检查
        path_check = self._check_path_safety(command, cwd)
        if not path_check["allowed"]:
            return ToolResult(
                success=False,
                error=f"Path check failed: {path_check['reason']}"
            )
        
        # 3. 权限检查
        if not context.is_admin:
            # 检查是否需要 admin 权限
            cmd_name = command.strip().split()[0] if command.strip() else ""
            if cmd_name in ADMIN_COMMANDS:
                return ToolResult(
                    success=False,
                    error=f"Command '{cmd_name}' requires admin privileges"
                )
        
        # 4. 执行命令
        try:
            result = await self._run_command(
                command,
                cwd=cwd,
                timeout=timeout,
                env=env
            )
            
            return ToolResult(
                success=result["returncode"] == 0,
                data={
                    "command": command,
                    "stdout": result["stdout"][:self.MAX_OUTPUT_SIZE],
                    "stderr": result["stderr"][:self.MAX_OUTPUT_SIZE],
                    "returncode": result["returncode"]
                },
                metadata={
                    "truncated": len(result["stdout"]) > self.MAX_OUTPUT_SIZE,
                    "timeout": result.get("timeout", False)
                }
            )
            
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Command timeout after {timeout} seconds",
                metadata={"timeout": True}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _check_command_security(self, command: str) -> Dict[str, Any]:
        """命令安全检查"""
        cmd_lower = command.lower().strip()
        
        # 检查危险命令
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return {"allowed": False, "reason": f"Blocked command: {blocked}"}
        
        # 检查 fork bomb 模式
        if ':(){' in cmd_lower or ':(){' in command:
            return {"allowed": False, "reason": "Fork bomb detected"}
        
        # 检查管道到 shell 执行
        if ' | sh' in cmd_lower or ' | bash' in cmd_lower:
            # 警告但允许（可配置）
            pass
        
        return {"allowed": True, "reason": None}
    
    def _check_path_safety(self, command: str, cwd: str) -> Dict[str, Any]:
        """路径安全检查"""
        # 检查路径遍历
        if '../' in command:
            # 检查是否试图访问系统路径
            if '/etc/' in command or '/sys/' in command or '/proc/' in command:
                return {"allowed": False, "reason": "Access to system paths not allowed"}
        
        # 检查工作目录
        if cwd:
            cwd_path = Path(cwd)
            if not cwd_path.exists():
                return {"allowed": False, "reason": f"Working directory not found: {cwd}"}
        
        return {"allowed": True, "reason": None}
    
    async def _run_command(
        self,
        command: str,
        cwd: str = "/",
        timeout: int = 30,
        env: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """执行命令"""
        
        # 构建环境变量
        run_env = {}
        if env:
            run_env.update(env)
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=run_env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                return {
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "returncode": process.returncode,
                    "timeout": False
                }
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise asyncio.TimeoutError()
                
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "timeout": False
            }
    
    def is_read_only(self) -> bool:
        """判断是否为只读命令"""
        # 如果命令只包含读操作，返回 True
        return False  # Shell 命令默认不安全