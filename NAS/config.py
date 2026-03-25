# 私有云相册NAS系统配置
import os

SECRET_KEY = 'album_nas_secret_key_2026_change_this'

# MySQL数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Love@5722',
    'database': 'album_nas',
    'charset': 'utf8mb4'
}

# 上传目录
UPLOAD_DIR = '/mnt/windows_share/album_nas/uploads'