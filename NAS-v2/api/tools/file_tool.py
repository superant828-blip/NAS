"""
文件操作工具集
基于 Claude Code FileEditTool, BashTool 架构设计
"""
import os
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseTool, ReadOnlyTool, WriteTool, DangerousTool, ToolContext, ToolResult


# 危险文件/目录黑名单
DANGEROUS_FILES = {
    '.gitconfig', '.bashrc', '.bash_profile',
    '.zshrc', '.zprofile', '.profile',
    '.ripgreprc', '.mcp.json', '.claude.json',
    '.gitmodules', '.ssh', 'id_rsa', 'id_ed25519'
}

DANGEROUS_DIRECTORIES = {
    '.git', '.vscode', '.idea', '.claude',
    'node_modules', '__pycache__', '.venv',
    'venv', '.env', 'etc', 'sys', 'proc'
}

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'pdf',
    'doc', 'docx', 'zip', 'rar', 'txt', 'mp3', 'wav',
    'apk', 'exe', 'csv', 'xls', 'xlsx', 'ppt', 'pptx',
    'json', 'xml', 'html', 'css', 'js', 'svg', 'ico'
}


class FileListTool(ReadOnlyTool):
    """文件列表工具"""
    
    name = "file_list"
    description = "列出目录中的文件和文件夹"
    
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径"},
            "show_hidden": {"type": "boolean", "description": "显示隐藏文件"},
            "sort_by": {"type": "string", "enum": ["name", "size", "date", "type"]},
            "order": {"type": "string", "enum": ["asc", "desc"]}
        },
        "required": ["path"]
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        path = Path(input_data.get("path", "/"))
        show_hidden = input_data.get("show_hidden", False)
        sort_by = input_data.get("sort_by", "name")
        order = input_data.get("order", "asc")
        
        # 路径检查
        if not path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")
        
        if not path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")
        
        # 权限检查
        allowed, reason = self._check_path_permission(path, context)
        if not allowed:
            return ToolResult(success=False, error=reason)
        
        try:
            items = []
            for item in path.iterdir():
                if not show_hidden and item.name.startswith('.'):
                    continue
                    
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "is_folder": item.is_dir(),
                    "size": stat.st_size if item.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:]
                })
            
            # 排序
            reverse = order == "desc"
            if sort_by == "name":
                items.sort(key=lambda x: x["name"], reverse=reverse)
            elif sort_by == "size":
                items.sort(key=lambda x: x["size"], reverse=reverse)
            elif sort_by == "date":
                items.sort(key=lambda x: x["modified"], reverse=reverse)
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "items": items,
                    "total": len(items)
                }
            )
            
        except PermissionError:
            return ToolResult(success=False, error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _check_path_permission(self, path: Path, context: ToolContext) -> tuple[bool, Optional[str]]:
        """检查路径权限"""
        path_str = str(path)
        
        # 检查危险目录
        for danger_dir in DANGEROUS_DIRECTORIES:
            if f"/{danger_dir}" in path_str or path_str.endswith(danger_dir):
                return False, f"Access denied to dangerous directory: {danger_dir}"
        
        # 检查允许路径
        if context.allowed_paths:
            allowed = any(path_str.startswith(p) for p in context.allowed_paths)
            if not allowed:
                return False, "Path not in allowed paths"
        
        return True, None


class FileReadTool(ReadOnlyTool):
    """文件读取工具"""
    
    name = "file_read"
    description = "读取文件内容"
    
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "offset": {"type": "integer", "description": "读取偏移量"},
            "limit": {"type": "integer", "description": "读取行数"},
            "encoding": {"type": "string", "description": "文件编码"}
        },
        "required": ["path"]
    }
    
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        path = Path(input_data.get("path"))
        offset = input_data.get("offset", 0)
        limit = input_data.get("limit", 1000)
        encoding = input_data.get("encoding", "utf-8")
        
        # 路径验证
        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        
        if not path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")
        
        # 大小检查
        if path.stat().st_size > self.MAX_SIZE:
            return ToolResult(
                success=False,
                error=f"File too large: {path.stat().st_size} bytes (max {self.MAX_SIZE})"
            )
        
        # 权限检查
        allowed, reason = self._check_path_permission(path, context)
        if not allowed:
            return ToolResult(success=False, error=reason)
        
        try:
            # 读取文件
            content = path.read_text(encoding=encoding)
            lines = content.split('\n')
            
            # 分页
            total_lines = len(lines)
            if offset > 0 or limit < total_lines:
                lines = lines[offset:offset + limit]
            
            # 计算哈希
            file_hash = hashlib.md5(content.encode()).hexdigest()
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "content": '\n'.join(lines),
                    "lines": len(lines),
                    "total_lines": total_lines,
                    "offset": offset,
                    "size": path.stat().st_size,
                    "hash": file_hash,
                    "encoding": encoding
                },
                metadata={
                    "truncated": offset + limit < total_lines
                }
            )
            
        except UnicodeDecodeError:
            return ToolResult(success=False, error="Unable to decode file - try binary mode")
        except PermissionError:
            return ToolResult(success=False, error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _check_path_permission(self, path: Path, context: ToolContext) -> tuple[bool, Optional[str]]:
        path_str = str(path)
        
        # 检查危险文件
        for danger_file in DANGEROUS_FILES:
            if path_str.endswith(danger_file):
                return False, f"Access denied to dangerous file: {danger_file}"
        
        return True, None


class FileWriteTool(WriteTool):
    """文件写入工具"""
    
    name = "file_write"
    description = "创建或写入文件内容"
    
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
            "encoding": {"type": "string", "description": "文件编码"},
            "create_parents": {"type": "boolean", "description": "创建父目录"}
        },
        "required": ["path", "content"]
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        path = Path(input_data.get("path"))
        content = input_data.get("content", "")
        encoding = input_data.get("encoding", "utf-8")
        create_parents = input_data.get("create_parents", True)
        
        # 路径安全检查
        allowed, reason = self._check_path_safety(path)
        if not allowed:
            return ToolResult(success=False, error=reason)
        
        # 权限检查
        if not context.is_admin and not str(path).startswith('/nas-pool'):
            return ToolResult(success=False, error="Write allowed only in /nas-pool")
        
        try:
            # 创建父目录
            if create_parents:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            path.write_text(content, encoding=encoding)
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "size": len(content),
                    "lines": len(content.split('\n'))
                },
                message=f"File written successfully"
            )
            
        except PermissionError:
            return ToolResult(success=False, error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _check_path_safety(self, path: Path) -> tuple[bool, Optional[str]]:
        path_str = str(path)
        
        # 路径遍历检查
        if '..' in path_str:
            return False, "Path traversal not allowed"
        
        # 危险路径
        if path_str.startswith('/etc') or path_str.startswith('/sys'):
            return False, "System paths not allowed"
        
        return True, None


class FileEditTool(WriteTool):
    """文件编辑工具"""
    
    name = "file_edit"
    description = "编辑文件内容（精确修改）"
    
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "search": {"type": "string", "description": "搜索内容"},
            "replace": {"type": "string", "description": "替换内容"},
            "replace_all": {"type": "boolean", "description": "替换所有匹配"},
            "line_number": {"type": "integer", "description": "行号编辑"}
        },
        "required": ["path", "search"]
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        path = Path(input_data.get("path"))
        search = input_data.get("search")
        replace = input_data.get("replace", "")
        replace_all = input_data.get("replace_all", False)
        
        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        
        try:
            content = path.read_text()
            original_content = content
            
            # 执行替换
            if replace_all:
                new_content = content.replace(search, replace)
                count = content.count(search)
            else:
                if search in content:
                    new_content = content.replace(search, replace, 1)
                    count = 1
                else:
                    return ToolResult(success=False, error="Search pattern not found")
            
            # 检查是否有变化
            if new_content == original_content:
                return ToolResult(success=False, error="No changes made")
            
            # 备份
            backup_path = path.with_suffix(path.suffix + '.bak')
            backup_path.write_text(original_content)
            
            # 写入
            path.write_text(new_content)
            
            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "replacements": count,
                    "backup": str(backup_path)
                },
                message=f"Replaced {count} occurrence(s)"
            )
            
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileDeleteTool(DangerousTool):
    """文件删除工具"""
    
    name = "file_delete"
    description = "删除文件或目录"
    
    def __init__(self):
        super().__init__()
        self.danger_level = 4  # 高危险
    
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "待删除路径"},
            "recursive": {"type": "boolean", "description": "递归删除目录"},
            "force": {"type": "boolean", "description": "强制删除"}
        },
        "required": ["path"]
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        # 管理员权限要求
        if not context.is_admin:
            return ToolResult(
                success=False,
                error="File deletion requires admin privileges"
            )
        
        path = Path(input_data.get("path"))
        recursive = input_data.get("recursive", False)
        
        if not path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")
        
        # 危险路径检查
        path_str = str(path)
        if any(path_str.startswith(d) for d in ['/etc', '/sys', '/proc', '/boot']):
            return ToolResult(success=False, error="Cannot delete system paths")
        
        try:
            if path.is_dir():
                if recursive:
                    shutil.rmtree(path)
                else:
                    path.rmdir()
            else:
                path.unlink()
            
            return ToolResult(
                success=True,
                data={"path": str(path), "deleted": True},
                message=f"Deleted: {path}"
            )
            
        except Exception as e:
            return ToolResult(success=False, error=str(e))