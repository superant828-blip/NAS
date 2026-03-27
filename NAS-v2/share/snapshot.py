"""
ZFS 快照管理模块
"""
import subprocess
import re
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class ZFSSnapshot:
    """ZFS 快照信息"""
    name: str  # dataset@snapshot_name
    dataset: str
    snapshot_name: str
    used: str
    available: str
    referenced: str
    creation: str
    used_space: str = ""
    referenced_space: str = ""
    
    @property
    def full_name(self) -> str:
        """完整名称"""
        return f"{self.dataset}@{self.snapshot_name}"
    
    @property
    def pool(self) -> str:
        """所属池"""
        return self.dataset.split('/')[0] if '/' in self.dataset else self.dataset
    
    @property
    def creation_time(self) -> Optional[datetime]:
        """创建时间"""
        try:
            # 解析格式: Mon Dec 25 00:00:00 2023
            return datetime.strptime(self.creation, "%a %b %d %H:%M:%S %Y")
        except:
            return None


class SnapshotManager:
    """ZFS 快照管理器"""
    
    def __init__(self):
        pass
    
    def _run_cmd(self, cmd: List[str], check: bool = True) -> str:
        """执行命令"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if check and result.returncode != 0:
                raise RuntimeError(f"Command failed: {result.stderr}")
            return result.stdout
        except FileNotFoundError:
            # 命令不存在 (如zfs未安装)
            raise RuntimeError(f"Command not found: {cmd[0]}")
    
    def list_snapshots(self, pool: str = None, dataset: str = None) -> List[ZFSSnapshot]:
        """列出快照"""
        cmd = [
            "zfs", "list", "-r", "-t", "snapshot", "-o",
            "name,used,available,referenced,creation,usedspace,referenced",
            "-H"
        ]
        
        try:
            output = self._run_cmd(cmd)
        except RuntimeError:
            return []
        
        snapshots = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            
            parts = line.split('\t')
            if len(parts) >= 5:
                full_name = parts[0]
                
                # 解析 dataset@snapshot
                if '@' not in full_name:
                    continue
                
                dataset_name, snap_name = full_name.split('@', 1)
                
                # 过滤
                if pool and not dataset_name.startswith(pool):
                    continue
                if dataset and dataset_name != dataset:
                    continue
                
                snapshots.append(ZFSSnapshot(
                    name=full_name,
                    dataset=dataset_name,
                    snapshot_name=snap_name,
                    used=parts[1] if len(parts) > 1 else "",
                    available=parts[2] if len(parts) > 2 else "",
                    referenced=parts[3] if len(parts) > 3 else "",
                    creation=parts[4] if len(parts) > 4 else "",
                    used_space=parts[5] if len(parts) > 5 else "",
                    referenced_space=parts[6] if len(parts) > 6 else ""
                ))
        
        # 按创建时间倒序
        snapshots.sort(key=lambda x: x.creation_time or datetime.min, reverse=True)
        return snapshots
    
    def create_snapshot(self, dataset: str, name: str, recursive: bool = False) -> Dict:
        """创建快照
        
        Args:
            dataset: 数据集名称 (如 tank/data)
            name: 快照名称
            recursive: 是否递归创建子数据集快照
        """
        full_name = f"{dataset}@{name}"
        
        cmd = ["zfs", "snapshot"]
        if recursive:
            cmd.append("-r")
        cmd.append(full_name)
        
        try:
            self._run_cmd(cmd)
            return {
                "status": "success",
                "snapshot": full_name,
                "dataset": dataset,
                "name": name
            }
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def delete_snapshot(self, snapshot: str, recursive: bool = False) -> Dict:
        """删除快照"""
        cmd = ["zfs", "destroy"]
        if recursive:
            cmd.append("-r")
        cmd.append(snapshot)
        
        try:
            self._run_cmd(cmd)
            return {"status": "success", "snapshot": snapshot}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def rollback_snapshot(self, snapshot: str, force: bool = False) -> Dict:
        """回滚到快照
        
        Warning: 这会丢弃快照之后的全部更改!
        """
        cmd = ["zfs", "rollback"]
        if force:
            cmd.append("-r")
        cmd.append(snapshot)
        
        try:
            self._run_cmd(cmd)
            return {"status": "success", "snapshot": snapshot}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def clone_snapshot(self, snapshot: str, target_dataset: str) -> Dict:
        """克隆快照到新数据集"""
        cmd = ["zfs", "clone", snapshot, target_dataset]
        
        try:
            self._run_cmd(cmd)
            return {
                "status": "success",
                "snapshot": snapshot,
                "target": target_dataset
            }
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def get_snapshot_properties(self, snapshot: str) -> Dict:
        """获取快照属性"""
        try:
            output = self._run_cmd([
                "zfs", "get", "all", "-H", "-o", "property,value", snapshot
            ])
            
            props = {}
            for line in output.split('\n'):
                if '\t' in line:
                    key, value = line.split('\t', 1)
                    props[key] = value
            
            return {"status": "success", "snapshot": snapshot, "properties": props}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def set_snapshot_property(self, snapshot: str, key: str, value: str) -> Dict:
        """设置快照属性"""
        try:
            self._run_cmd(["zfs", "set", f"{key}={value}", snapshot])
            return {"status": "success", "property": key, "value": value}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def send_snapshot(self, snapshot: str, target: str, incremental: str = None) -> Dict:
        """发送快照
        
        Args:
            snapshot: 源快照
            target: 目标 (文件路径或远程主机)
            incremental: 增量发送的基础快照
        """
        cmd = ["zfs", "send"]
        if incremental:
            cmd.extend(["-i", incremental])
        cmd.append(snapshot)
        
        try:
            # 输出到目标
            if target.startswith('/'):
                # 本地文件
                with open(target, 'w') as f:
                    subprocess.run(cmd, stdout=f, timeout=300)
                return {"status": "success", "output": target}
            else:
                # 远程发送
                cmd.extend(["|", "ssh", target, "zfs", "receive", "-F", target])
                subprocess.run(cmd, timeout=300)
                return {"status": "success", "target": target}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Send timeout"}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def receive_snapshot(self, dataset: str, source: str) -> Dict:
        """接收快照"""
        cmd = ["zfs", "receive", "-F", dataset]
        
        try:
            if source.startswith('/'):
                # 从文件接收
                with open(source, 'r') as f:
                    subprocess.run(cmd, stdin=f, timeout=300)
            else:
                # 从远程接收
                cmd2 = ["ssh", source, "zfs", "send", source]
                proc1 = subprocess.Popen(cmd2, stdout=subprocess.PIPE)
                proc2 = subprocess.run(cmd, stdin=proc1.stdout, timeout=300)
            
            return {"status": "success", "dataset": dataset}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Receive timeout"}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def get_snapshot_space_usage(self, snapshot: str) -> Dict:
        """获取快照空间使用情况"""
        try:
            output = self._run_cmd([
                "zfs", "list", "-o", "name,used,referenced,usedspace,referenced", 
                "-H", snapshot
            ])
            
            parts = output.strip().split('\t')
            if len(parts) >= 4:
                return {
                    "snapshot": snapshot,
                    "used": parts[1] if len(parts) > 1 else "0",
                    "referenced": parts[2] if len(parts) > 2 else "0",
                    "used_space": parts[3] if len(parts) > 3 else "0",
                    "referenced_space": parts[4] if len(parts) > 4 else "0"
                }
        except:
            pass
        
        return {"snapshot": snapshot, "used": "0"}


# 全局快照管理器
snapshot_manager = SnapshotManager()