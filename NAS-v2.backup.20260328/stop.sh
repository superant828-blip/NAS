#!/bin/bash
# NAS-v2 停止脚本
# 用法: ./stop.sh [options]
# Options:
#   -f, --force    强制停止 (SIGKILL)
#   -a, --all      停止所有相关进程
#   -h, --help     显示帮助

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FORCE=false
STOP_ALL=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force)
            FORCE=true
            shift
            ;;
        -a|--all)
            STOP_ALL=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [options]"
            echo "Options:"
            echo "  -f, --force    强制停止 (SIGKILL)"
            echo "  -a, --all      停止所有相关进程"
            echo "  -h, --help     显示帮助"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${RED}=== NAS-v2 停止脚本 ===${NC}"

# 查找进程
find_process() {
    pgrep -f "uvicorn api.main:app" 2>/dev/null || true
}

PID=$(find_process)

if [ -z "$PID" ]; then
    echo -e "${YELLOW}没有找到运行中的 NAS-v2 服务${NC}"
    exit 0
fi

if [ "$FORCE" = true ]; then
    echo -e "${YELLOW}强制停止进程 (PID: $PID)${NC}"
    kill -9 $PID 2>/dev/null || true
else
    echo -e "${YELLOW}停止进程 (PID: $PID)${NC}"
    kill $PID 2>/dev/null || true
    
    # 等待进程结束
    for i in {1..5}; do
        if ! kill -0 $PID 2>/dev/null; then
            break
        fi
        sleep 1
    done
    
    # 如果进程仍然存在，强制停止
    if kill -0 $PID 2>/dev/null; then
        echo -e "${YELLOW}进程仍未停止，强制终止...${NC}"
        kill -9 $PID 2>/dev/null || true
    fi
fi

echo -e "${GREEN}✓ 服务已停止${NC}"

# 可选：停止所有相关进程
if [ "$STOP_ALL" = true ]; then
    echo -e "${YELLOW}停止所有相关进程...${NC}"
    pkill -f "api.main:app" 2>/dev/null || true
    pkill -f "nas-v2" 2>/dev/null || true
    echo -e "${GREEN}✓ 所有进程已停止${NC}"
fi

exit 0