"""
ZFS 存储管理模块
基于 TrueNAS 架构的简化版
"""
import subprocess
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class ZFSPool:
    """ZFS 池信息"""
    name: str
    size: str
    allocated: str
    free: str
    cap: str  # capacity
    health: str
    altroot: str = ""
    autotrim: str = "off"
    
    @property
    def usage_percent(self) -> int:
        """使用率百分比"""
        try:
            return int(self.cap.rstrip('%'))
        except:
            return 0


@dataclass
class ZFSDataset:
    """ZFS 数据集信息"""
    name: str
    pool: str
    used: str
    available: str
    referenced: str
    mountpoint: str
    compression: str = "off"
    dedup: str = "off"
    readonly: str = "off"
    atime: str = "on"
    quota: str = "none"
    reservation: str = "none"
    snapdir: str = "hidden"
    
    @property
    def parent(self) -> str:
        """父数据集"""
        parts = self.name.split('/')
        if len(parts) > 1:
            return '/'.join(parts[:-1])
        return ""
    
    @property
    def is_snapshot(self) -> bool:
        """是否为快照"""
        return '@' in self.name


@dataclass  
class ZFSDisk:
    """ZFS 池中的磁盘"""
    device: str
    pool: str
    state: str
    size: str
    read_errors: int = 0
    write_errors: int = 0
    checksum_errors: int = 0


class ZFSManager:
    """ZFS 存储管理器"""
    
    def __init__(self, mount_root: str = "/mnt"):
        self.mount_root = mount_root
    
    def _run_cmd(self, cmd: List[str], check: bool = True) -> str:
        """执行命令"""
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if check and result.returncode != 0:
                raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
            return result.stdout.strip()
        except FileNotFoundError:
            # 命令不存在 (如zpool/zfs未安装)
            raise RuntimeError(f"Command not found: {cmd[0]}")
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Command timeout: {' '.join(cmd)}")
    
    def list_pools(self) -> List[ZFSPool]:
        """列出所有 ZFS 池"""
        try:
            output = self._run_cmd(["zpool", "list", "-o", 
                "name,size,allocated,free,cap,health,altroot,autotrim", "-H"])
        except RuntimeError:
            return []
        
        pools = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) >= 6:
                pools.append(ZFSPool(
                    name=parts[0],
                    size=parts[1],
                    allocated=parts[2],
                    free=parts[3],
                    cap=parts[4],
                    health=parts[5],
                    altroot=parts[6] if len(parts) > 6 else "",
                    autotrim=parts[7] if len(parts) > 7 else "off"
                ))
        return pools
    
    def get_pool(self, name: str) -> Optional[ZFSPool]:
        """获取指定池信息"""
        pools = self.list_pools()
        for p in pools:
            if p.name == name:
                return p
        return None
    
    def create_pool(self, name: str, vdevs: List[str], 
                    layout: str = "basic") -> Dict:
        """
        创建 ZFS 池
        
        Args:
            name: 池名称
            vdevs: 磁盘列表
            layout: 布局类型 (basic, mirror, raidz1, raidz2)
        """
        if layout == "basic":
            vdev_str = " ".join(vdevs)
            cmd = ["zpool", "create", "-f", name, vdev_str]
        elif layout == "mirror":
            vdev_str = "mirror " + " ".join(vdevs)
            cmd = ["zpool", "create", "-f", name, vdev_str]
        elif layout == "raidz1":
            vdev_str = "raidz1 " + " ".join(vdevs)
            cmd = ["zpool", "create", "-f", name, vdev_str]
        else:
            raise ValueError(f"Unsupported layout: {layout}")
        
        try:
            self._run_cmd(cmd)
            return {"status": "success", "pool": name}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def destroy_pool(self, name: str, force: bool = False) -> Dict:
        """删除 ZFS 池"""
        cmd = ["zpool", "destroy"]
        if force:
            cmd.append("-f")
        cmd.append(name)
        
        try:
            self._run_cmd(cmd)
            return {"status": "success", "pool": name}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def import_pool(self, name: str, force: bool = False) -> Dict:
        """导入 ZFS 池"""
        cmd = ["zpool", "import"]
        if force:
            cmd.append("-f")
        cmd.append(name)
        
        try:
            self._run_cmd(cmd)
            return {"status": "success", "pool": name}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def export_pool(self, name: str) -> Dict:
        """导出 ZFS 池"""
        try:
            self._run_cmd(["zpool", "export", name])
            return {"status": "success", "pool": name}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def list_datasets(self, pool: str = None) -> List[ZFSDataset]:
        """列出数据集"""
        try:
            output = self._run_cmd([
                "zfs", "list", "-r", "-o",
                "name,pool,used,available,referenced,mountpoint,"
                "compression,dedup,readonly,atime,quota,reservation,snapdir",
                "-H", "-t", "filesystem"
            ])
        except RuntimeError:
            return []
        
        datasets = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) >= 6:
                ds = ZFSDataset(
                    name=parts[0],
                    pool=parts[1],
                    used=parts[2],
                    available=parts[3],
                    referenced=parts[4],
                    mountpoint=parts[5],
                    compression=parts[6] if len(parts) > 6 else "off",
                    dedup=parts[7] if len(parts) > 7 else "off",
                    readonly=parts[8] if len(parts) > 8 else "off",
                    atime=parts[9] if len(parts) > 9 else "on",
                    quota=parts[10] if len(parts) > 10 else "none",
                    reservation=parts[11] if len(parts) > 11 else "none",
                    snapdir=parts[12] if len(parts) > 12 else "hidden"
                )
                if pool is None or ds.pool == pool:
                    datasets.append(ds)
        return datasets
    
    def create_dataset(self, name: str, properties: Dict = None) -> Dict:
        """创建数据集"""
        try:
            self._run_cmd(["zfs", "create", name])
            
            if properties:
                for k, v in properties.items():
                    self._run_cmd(["zfs", "set", f"{k}={v}", name])
            
            return {"status": "success", "dataset": name}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def destroy_dataset(self, name: str, force: bool = False, recursive: bool = False) -> Dict:
        """删除数据集"""
        cmd = ["zfs", "destroy"]
        if force:
            cmd.append("-f")
        if recursive:
            cmd.append("-r")
        cmd.append(name)
        
        try:
            self._run_cmd(cmd)
            return {"status": "success", "dataset": name}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def set_property(self, dataset: str, key: str, value: str) -> Dict:
        """设置数据集属性"""
        try:
            self._run_cmd(["zfs", "set", f"{key}={value}", dataset])
            return {"status": "success", "dataset": dataset, "property": key, "value": value}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def get_property(self, dataset: str, key: str) -> Optional[str]:
        """获取数据集属性"""
        try:
            output = self._run_cmd(["zfs", "get", "-H", "-o", "value", key, dataset])
            return output.strip()
        except:
            return None
    
    def get_pool_status(self, pool: str) -> Dict:
        """获取池详细状态"""
        try:
            output = self._run_cmd(["zpool", "status", "-v", pool])
            return {"status": "success", "output": output}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def scrub_pool(self, pool: str) -> Dict:
        """启动池清理"""
        try:
            self._run_cmd(["zpool", "scrub", pool])
            return {"status": "success", "pool": pool, "action": "scrub started"}
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
    
    def get_disk_info(self, pool: str) -> List[ZFSDisk]:
        """获取池中磁盘信息"""
        try:
            output = self._run_cmd(["zpool", "status", "-v", pool])
        except:
            return []
        
        disks = []
        # 解析 zpool status 输出
        in_config = False
        for line in output.split('\n'):
            if 'config' in line.lower():
                in_config = True
                continue
            if in_config and line.strip():
                # 解析磁盘行
                match = re.match(r'(\S+)\s+(ONLINE|FAULTED|UNAVAIL|REMOVED)\s+(\S+)', line)
                if match:
                    disks.append(ZFSDisk(
                        device=match.group(1),
                        pool=pool,
                        state=match.group(2),
                        size=match.group(3)
                    ))
        return disks


# 全局 ZFS 管理器实例
zfs_manager = ZFSManager()