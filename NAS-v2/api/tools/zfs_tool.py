"""
ZFS 管理工具
"""
import subprocess
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base import BaseTool, ReadOnlyTool, WriteTool, ToolContext, ToolResult


class ZFSListTool(ReadOnlyTool):
    """ZFS 列表工具"""
    
    name = "zfs_list"
    description = "列出 ZFS 数据集和快照"
    
    input_schema = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["filesystem", "snapshot", "volume", "all"]},
            "dataset": {"type": "string", "description": "数据集名称"}
        }
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        zfs_type = input_data.get("type", "all")
        dataset = input_data.get("dataset", "")
        
        try:
            # 检查 ZFS 是否可用
            check = await self._check_zfs_available()
            if not check["available"]:
                return ToolResult(
                    success=False,
                    error=check["error"],
                    data={"available": False}
                )
            
            # 构建命令
            cmd = ["zfs", "list", "-r", "-o", "name,used,available,referenced,mountpoint,compression"]
            
            if dataset:
                cmd.append(dataset)
            
            if zfs_type == "filesystem":
                cmd.extend(["-t", "filesystem"])
            elif zfs_type == "snapshot":
                cmd.extend(["-t", "snapshot"])
            
            result = await self._run_command(cmd)
            
            if result["returncode"] != 0:
                return ToolResult(
                    success=False,
                    error=result["stderr"]
                )
            
            # 解析输出
            datasets = self._parse_list_output(result["stdout"])
            
            return ToolResult(
                success=True,
                data={
                    "datasets": datasets,
                    "count": len(datasets)
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _check_zfs_available(self) -> Dict[str, Any]:
        """检查 ZFS 是否可用"""
        try:
            result = await self._run_command(["zfs", "list"])
            if result["returncode"] == 0:
                return {"available": True}
            return {"available": False, "error": "ZFS not available"}
        except FileNotFoundError:
            return {"available": False, "error": "ZFS command not found"}
    
    def _parse_list_output(self, output: str) -> List[Dict[str, Any]]:
        """解析 zfs list 输出"""
        lines = output.strip().split('\n')
        if len(lines) < 2:
            return []
        
        # 解析表头
        headers = lines[0].split()
        
        # 解析数据行
        datasets = []
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= len(headers):
                dataset = {}
                for i, header in enumerate(headers):
                    dataset[header.lower()] = parts[i] if i < len(parts) else ""
                datasets.append(dataset)
        
        return datasets
    
    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """执行命令"""
        import asyncio
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            return {
                "stdout": stdout.decode('utf-8'),
                "stderr": stderr.decode('utf-8'),
                "returncode": process.returncode
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }


class ZFSSnapshotTool(WriteTool):
    """ZFS 快照工具"""
    
    name = "zfs_snapshot"
    description = "创建和管理 ZFS 快照"
    
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "list", "delete", "rollback"]},
            "dataset": {"type": "string", "description": "数据集名称"},
            "snapshot_name": {"type": "string", "description": "快照名称"},
            "recursive": {"type": "boolean", "description": "递归处理"}
        },
        "required": ["action", "dataset"]
    }
    
    async def execute(self, input_data: Dict[str, Any], context: ToolContext) -> ToolResult:
        action = input_data.get("action")
        dataset = input_data.get("dataset")
        snapshot_name = input_data.get("snapshot_name")
        recursive = input_data.get("recursive", False)
        
        if not context.is_admin:
            return ToolResult(
                success=False,
                error="ZFS operations require admin privileges"
            )
        
        try:
            if action == "create":
                return await self._create_snapshot(dataset, snapshot_name, recursive)
            elif action == "list":
                return await self._list_snapshots(dataset)
            elif action == "delete":
                return await self._delete_snapshot(dataset, snapshot_name)
            elif action == "rollback":
                return await self._rollback_snapshot(dataset, snapshot_name)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _create_snapshot(
        self,
        dataset: str,
        snapshot_name: str,
        recursive: bool
    ) -> ToolResult:
        """创建快照"""
        cmd = ["zfs", "snapshot"]
        
        if recursive:
            cmd.append("-r")
        
        cmd.append(f"{dataset}@{snapshot_name}")
        
        result = await self._run_command(cmd)
        
        if result["returncode"] != 0:
            return ToolResult(success=False, error=result["stderr"])
        
        return ToolResult(
            success=True,
            data={
                "dataset": dataset,
                "snapshot": f"{dataset}@{snapshot_name}",
                "created": True
            },
            message=f"Snapshot created: {dataset}@{snapshot_name}"
        )
    
    async def _list_snapshots(self, dataset: str) -> ToolResult:
        """列出快照"""
        cmd = ["zfs", "list", "-t", "snapshot", "-r", "-o", "name,used,creation", dataset]
        
        result = await self._run_command(cmd)
        
        if result["returncode"] != 0:
            return ToolResult(success=False, error=result["stderr"])
        
        snapshots = self._parse_snapshot_output(result["stdout"])
        
        return ToolResult(
            success=True,
            data={
                "snapshots": snapshots,
                "count": len(snapshots)
            }
        )
    
    async def _delete_snapshot(self, dataset: str, snapshot_name: str) -> ToolResult:
        """删除快照"""
        cmd = ["zfs", "destroy", "-r", f"{dataset}@{snapshot_name}"]
        
        result = await self._run_command(cmd)
        
        if result["returncode"] != 0:
            return ToolResult(success=False, error=result["stderr"])
        
        return ToolResult(
            success=True,
            data={"deleted": True},
            message=f"Snapshot deleted: {dataset}@{snapshot_name}"
        )
    
    async def _rollback_snapshot(self, dataset: str, snapshot_name: str) -> ToolResult:
        """回滚快照"""
        cmd = ["zfs", "rollback", "-r", f"{dataset}@{snapshot_name}"]
        
        result = await self._run_command(cmd)
        
        if result["returncode"] != 0:
            return ToolResult(success=False, error=result["stderr"])
        
        return ToolResult(
            success=True,
            data={"rolled_back": True},
            message=f"Rolled back to: {dataset}@{snapshot_name}"
        )
    
    def _parse_snapshot_output(self, output: str) -> List[Dict[str, Any]]:
        """解析快照输出"""
        lines = output.strip().split('\n')
        if len(lines) < 2:
            return []
        
        snapshots = []
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                name_parts = parts[0].split('@')
                snapshots.append({
                    "dataset": name_parts[0] if len(name_parts) > 0 else "",
                    "snapshot": name_parts[1] if len(name_parts) > 1 else "",
                    "used": parts[1] if len(parts) > 1 else "",
                    "creation": parts[2] if len(parts) > 2 else ""
                })
        
        return snapshots
    
    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """执行命令"""
        import asyncio
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            return {
                "stdout": stdout.decode('utf-8'),
                "stderr": stderr.decode('utf-8'),
                "returncode": process.returncode
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }