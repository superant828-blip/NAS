"""
SMB/CIFS 共享模块
"""
import os
import subprocess
import configparser
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict


@dataclass
class SMBShare:
    """SMB 共享配置"""
    name: str
    path: str
    comment: str = ""
    browseable: bool = True
    writable: bool = True
    guest_ok: bool = False
    valid_users: str = ""
    readonly: bool = False
    create_mask: str = "0744"
    directory_mask: str = "0755"
    inherit_owner: bool = False
    inheritance: str = "full"  # full, none, acl
    
    def to_config(self) -> str:
        """转换为 smb.conf 格式"""
        lines = [
            f"[{self.name}]",
            f"    path = {self.path}",
            f"    comment = {self.comment or self.name}",
            f"    browseable = {'yes' if self.browseable else 'no'}",
            f"    writable = {'yes' if self.writable else 'no'}",
            f"    read only = {'yes' if self.readonly else 'no'}",
            f"    guest ok = {'yes' if self.guest_ok else 'no'}",
        ]
        if self.valid_users:
            lines.append(f"    valid users = {self.valid_users}")
        lines.extend([
            f"    create mask = {self.create_mask}",
            f"    directory mask = {self.directory_mask}",
        ])
        if self.inherit_owner:
            lines.append(f"    inherit owner = yes")
        if self.inheritance != "none":
            lines.append(f"    inherit permissions = yes")
        
        return '\n'.join(lines)


class SMBManager:
    """SMB 共享管理器"""
    
    def __init__(self, config_file: str = "/etc/samba/smb.conf"):
        self.config_file = config_file
        self.shares: Dict[str, SMBShare] = {}
        self._load_config()
    
    def _run_cmd(self, cmd: List[str], check: bool = True) -> str:
        """执行命令"""
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed: {result.stderr}")
        return result.stdout
    
    def _load_config(self):
        """加载现有配置"""
        if not os.path.exists(self.config_file):
            return
        
        config = configparser.ConfigParser(allow_no_value=True)
        config.read(self.config_file)
        
        for section in config.sections():
            if section in ['global', 'homes', 'printers']:
                continue
            self.shares[section] = SMBShare(
                name=section,
                path=config.get(section, 'path', fallback=''),
                comment=config.get(section, 'comment', fallback=''),
                browseable=config.get(section, 'browseable', fallback='yes') == 'yes',
                writable=config.get(section, 'writable', fallback='yes') == 'yes',
                guest_ok=config.get(section, 'guest ok', fallback='no') == 'yes',
                valid_users=config.get(section, 'valid users', fallback=''),
            )
    
    def list_shares(self) -> List[SMBShare]:
        """列出所有共享"""
        return list(self.shares.values())
    
    def get_share(self, name: str) -> Optional[SMBShare]:
        """获取共享配置"""
        return self.shares.get(name)
    
    def create_share(self, share: SMBShare) -> Dict:
        """创建 SMB 共享"""
        # 检查路径是否存在
        if not os.path.exists(share.path):
            # 创建目录
            try:
                os.makedirs(share.path, exist_ok=True)
            except OSError as e:
                return {"status": "error", "message": f"Cannot create path: {e}"}
        
        # 检查目录权限
        if not os.access(share.path, os.R_OK | os.W_OK):
            # 尝试设置权限
            try:
                os.chmod(share.path, 0o755)
            except OSError:
                pass
        
        self.shares[share.name] = share
        
        # 写入配置文件
        if self._write_config():
            # 重新加载 Samba 配置
            self._reload_samba()
            return {"status": "success", "share": asdict(share)}
        
        return {"status": "error", "message": "Failed to write config"}
    
    def update_share(self, name: str, updates: Dict) -> Dict:
        """更新共享配置"""
        if name not in self.shares:
            return {"status": "error", "message": "Share not found"}
        
        share = self.shares[name]
        for k, v in updates.items():
            if hasattr(share, k):
                setattr(share, k, v)
        
        if self._write_config():
            self._reload_samba()
            return {"status": "success", "share": asdict(share)}
        
        return {"status": "error", "message": "Failed to update"}
    
    def delete_share(self, name: str) -> Dict:
        """删除共享"""
        if name not in self.shares:
            return {"status": "error", "message": "Share not found"}
        
        del self.shares[name]
        
        if self._write_config():
            self._reload_samba()
            return {"status": "success", "share": name}
        
        return {"status": "error", "message": "Failed to delete"}
    
    def _write_config(self) -> bool:
        """写入 Samba 配置"""
        try:
            # 读取现有全局配置
            global_config = ""
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    content = f.read()
                # 提取 [global] 部分
                lines = content.split('\n')
                in_global = False
                for line in lines:
                    if line.strip() == '[global]':
                        in_global = True
                    if in_global and line.startswith('[') and line != '[global]':
                        in_global = False
                    if in_global or not line.startswith('['):
                        global_config += line + '\n'
            
            # 生成新配置
            config = global_config + '\n'
            for share in self.shares.values():
                config += share.to_config() + '\n\n'
            
            # 写入
            with open(self.config_file, 'w') as f:
                f.write(config)
            
            return True
        except Exception as e:
            print(f"Error writing config: {e}")
            return False
    
    def _reload_samba(self):
        """重新加载 Samba 配置"""
        try:
            # 尝试使用 smbcontrol
            subprocess.run(["smbcontrol", "smbd", "reload-config"], 
                         capture_output=True, timeout=5)
        except:
            # 备用方案：重新启动 smbd
            try:
                subprocess.run(["systemctl", "reload", "smbd"], 
                             capture_output=True, timeout=5)
            except:
                pass
    
    def get_status(self) -> Dict:
        """获取 Samba 服务状态"""
        try:
            result = subprocess.run(
                ["smbstatus", "--brief"], 
                capture_output=True, text=True, timeout=5
            )
            return {
                "status": "running",
                "output": result.stdout
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        except FileNotFoundError:
            return {"status": "not_installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def start_service(self) -> Dict:
        """启动 Samba 服务"""
        try:
            subprocess.run(["systemctl", "start", "smbd"], 
                         capture_output=True, timeout=10)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def stop_service(self) -> Dict:
        """停止 Samba 服务"""
        try:
            subprocess.run(["systemctl", "stop", "smbd"], 
                         capture_output=True, timeout=10)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# 全局 SMB 管理器
smb_manager = SMBManager()