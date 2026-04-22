"""
NAS 核心配置模块
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# 项目根目录
NAS_ROOT = Path(__file__).parent.parent
DATA_DIR = NAS_ROOT / "data"
CONFIG_DIR = NAS_ROOT / "config"
CACHE_DIR = NAS_ROOT / "cache"
LOG_DIR = NAS_ROOT / "logs"  # 新增日志目录

# 确保目录存在
for d in [DATA_DIR, CONFIG_DIR, CACHE_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

@dataclass
class NASConfig:
    """NAS 系统配置"""
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # 安全配置
    secret_key: str = ""
    token_expire_minutes: int = 60 * 24  # 24小时
    session_timeout: int = 3600
    
    # 存储配置
    default_pool: str = "tank"
    default_dataset: str = "data"
    zfs_mount_root: str = "/mnt"
    
    # 共享配置
    smb_config: str = "/etc/samba/smb.conf"
    nfs_exports: str = "/etc/exports"
    nfsd_threads: int = 4
    
    # 数据库配置
    db_type: str = "sqlite"  # sqlite 或 mysql
    db_path: str = "data/nas.db"
    
    # 上传配置
    upload_dir: str = "uploads"
    allowed_extensions: set = None  # 运行时设置
    
    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'pdf', 'doc', 'docx', 'zip', 'rar', 'txt', 'mp3', 'wav', 'apk', 'exe', 'csv', 'xls', 'xlsx', 'ppt', 'pptx', 'json', 'xml', 'html', 'css', 'js', 'svg', 'ico', 'bmp', 'tiff', 'flac', 'aac', 'ogg', 'wma', 'mov', 'avi', 'mkv', 'wmv', 'flv', '7z', 'tar', 'gz', 'bz2', 'iso', 'dmg', 'img', 'bin'}
    
    # MySQL 配置
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "nas"
    mysql_password: str = ""
    mysql_database: str = "nas_db"
    
    @classmethod
    def load(cls) -> 'NASConfig':
        """加载配置"""
        config = cls()
        
        # 从环境变量覆盖
        config.host = os.getenv("NAS_HOST", config.host)
        config.port = int(os.getenv("NAS_PORT", config.port))
        config.debug = os.getenv("NAS_DEBUG", "").lower() == "true"
        config.secret_key = os.getenv("NAS_SECRET_KEY", config.secret_key or os.urandom(32).hex())
        
        # 数据库配置
        config.db_type = os.getenv("DB_TYPE", config.db_type)
        config.db_path = os.getenv("DB_PATH", config.db_path)
        config.mysql_host = os.getenv("MYSQL_HOST", config.mysql_host)
        config.mysql_port = int(os.getenv("MYSQL_PORT", config.mysql_port))
        config.mysql_user = os.getenv("MYSQL_USER", config.mysql_user)
        config.mysql_password = os.getenv("MYSQL_PASSWORD", config.mysql_password)
        config.mysql_database = os.getenv("MYSQL_DATABASE", config.mysql_database)
        
        # 生成默认密钥文件
        config_file = CONFIG_DIR / "secret.key"
        if not config_file.exists() and not config.secret_key:
            config.secret_key = os.urandom(32).hex()
            config_file.write_text(config.secret_key)
        elif config_file.exists() and not config.secret_key:
            config.secret_key = config_file.read_text().strip()
        
        return config

# 全局配置实例
config = NASConfig.load()