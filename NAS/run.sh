#!/bin/bash
cd ~/.openclaw/workspace/NAS

# 停止旧进程
pkill -f "python3 app_flask.py" 2>/dev/null
sleep 1

# 确保目录存在
mkdir -p ~/.openclaw/workspace/NAS/album_nas/uploads
mkdir -p ~/.openclaw/workspace/NAS/public

# 启动
echo "🚀 启动NAS服务..."
python3 app_flask.py
