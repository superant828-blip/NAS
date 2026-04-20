#!/bin/bash
# NAS-v2 快速启动脚本
# 用法: ./start.sh [options]
# Options:
#   -d, --detach    后台运行
#   -p, --prod      生产模式启动
#   -h, --help      显示帮助

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 默认配置
DETACH=false
PROD=false
PORT=8003

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--detach)
            DETACH=true
            shift
            ;;
        -p|--prod)
            PROD=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [options]"
            echo "Options:"
            echo "  -d, --detach    后台运行"
            echo "  -p, --prod      生产模式启动"
            echo "  -h, --help      显示帮助"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}=== NAS-v2 启动脚本 ===${NC}"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}安装依赖...${NC}"
    pip install -r requirements.txt -q
fi

# 检查端口是否被占用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}错误: 端口 $PORT 已被占用${NC}"
    echo "请先停止现有服务: ./stop.sh"
    exit 1
fi

# 启动服务
if [ "$PROD" = true ]; then
    echo -e "${GREEN}生产模式启动 (端口 $PORT)${NC}"
    if [ "$DETACH" = true ]; then
        nohup uvicorn api.main:app --host 0.0.0.0 --port $PORT > nas-v2.log 2>&1 &
        echo -e "${GREEN}✓ 服务已启动 (PID: $!)${NC}"
        echo "日志文件: nas-v2.log"
    else
        exec uvicorn api.main:app --host 0.0.0.0 --port $PORT
    fi
else
    echo -e "${GREEN}开发模式启动 (端口 $PORT)${NC}"
    if [ "$DETACH" = true ]; then
        nohup uvicorn api.main:app --host 0.0.0.0 --port $PORT --reload > nas-v2.log 2>&1 &
        echo -e "${GREEN}✓ 服务已启动 (PID: $!)${NC}"
        echo "日志文件: nas-v2.log"
    else
        exec uvicorn api.main:app --host 0.0.0.0 --port $PORT --reload
    fi
fi

echo -e "${GREEN}=== 启动完成 ===${NC}"
echo "访问: http://localhost:$PORT"