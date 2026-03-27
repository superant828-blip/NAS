#!/bin/bash
# NAS项目自动优化提交脚本

cd ~/.openclaw/workspace/NAS

echo "=== NAS自动提交工具 ==="
echo ""

# 核心文件
CORE_FILES="app_flask.py public/ .gitignore database.sql config.py"

# 检查修改
echo "📝 检查核心文件修改..."
for f in $CORE_FILES; do
    if [ -e "$f" ]; then
        git add "$f" 2>/dev/null
    fi
done

# 检查状态
if git diff --staged --quiet; then
    echo "没有新修改需要提交"
    exit 0
fi

# 提交
COMMIT_MSG="optimize: $(date '+%Y-%m-%d %H:%M') 自动优化"
git commit -m "$COMMIT_MSG"

# 推送
echo "🚀 推送到GitHub..."
git push origin master

echo ""
echo "=== ✅ 完成 ==="
