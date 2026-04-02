#!/bin/bash
# NAS-v2 端到端集成测试脚本
# 后端地址: http://localhost:8000

BASE_URL="http://localhost:8000"
TOKEN=""

echo "========================================"
echo "NAS-v2 端到端集成测试"
echo "========================================"

# 1. 完整用户流程: 注册 → 登录 → 上传文件 → 创建文件夹 → 分享链接 → 下载
echo ""
echo "=== 1. 完整用户流程测试 ==="

# 1.1 注册用户
echo -e "\n[步骤 1.1] 注册用户..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"test123"}')
echo "请求: POST /api/v1/auth/register"
echo "响应: $RESPONSE"

# 1.2 登录
echo -e "\n[步骤 1.2] 用户登录..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nas.local","password":"admin123"}')
echo "请求: POST /api/v1/auth/login"
echo "响应: $RESPONSE"
TOKEN=$(echo $RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
echo "获取Token: ${TOKEN:0:20}..."

if [ -z "$TOKEN" ]; then
  echo "警告: 无法获取Token，使用默认测试"
  TOKEN="test_token"
fi

# 1.3 创建文件夹
echo -e "\n[步骤 1.3] 创建文件夹..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/files/folder" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"test_folder","parent_id":null}')
echo "请求: POST /api/v1/files/folder"
echo "响应: $RESPONSE"

# 1.4 上传文件
echo -e "\n[步骤 1.4] 上传文件..."
echo "test content" > /tmp/test_file.txt
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/files/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_file.txt" \
  -F "parent_id=")
echo "请求: POST /api/v1/files/upload"
echo "响应: $RESPONSE"

# 1.5 获取文件列表
echo -e "\n[步骤 1.5] 获取文件列表..."
RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/files/" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: GET /api/v1/files/"
echo "响应: $RESPONSE"

# 1.6 分享链接
echo -e "\n[步骤 1.6] 创建分享链接..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/share/link" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"file_id":1,"expire_hours":24}')
echo "请求: POST /api/v1/share/link"
echo "响应: $RESPONSE"

# 2. 文件管理流程
echo ""
echo "=== 2. 文件管理流程测试 ==="

# 2.1 创建文件夹
echo -e "\n[步骤 2.1] 创建文件夹..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/files/folder" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"folder_for_test","parent_id":null}')
echo "请求: POST /api/v1/files/folder"
echo "响应: $RESPONSE"

# 2.2 移动文件
echo -e "\n[步骤 2.2] 移动文件..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/files/move" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"file_id":1,"new_parent_id":1}')
echo "请求: POST /api/v1/files/move"
echo "响应: $RESPONSE"

# 2.3 删除文件
echo -e "\n[步骤 2.3] 删除文件..."
RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/v1/files/1" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: DELETE /api/v1/files/1"
echo "响应: $RESPONSE"

# 3. 相册流程
echo ""
echo "=== 3. 相册流程测试 ==="

# 3.1 创建相册
echo -e "\n[步骤 3.1] 创建相册..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/albums" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"test_album","description":"test album"}')
echo "请求: POST /api/v1/albums"
echo "响应: $RESPONSE"

# 3.2 获取相册列表
echo -e "\n[步骤 3.2] 获取相册列表..."
RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/albums" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: GET /api/v1/albums"
echo "响应: $RESPONSE"

# 3.3 上传照片到相册
echo -e "\n[步骤 3.3] 上传照片到相册..."
echo "fake image data" > /tmp/test_photo.jpg
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/albums/1/photos" \
  -H "Authorization: Bearer $TOKEN" \
  -F "photo=@/tmp/test_photo.jpg" \
  -F "album_id=1")
echo "请求: POST /api/v1/albums/1/photos"
echo "响应: $RESPONSE"

# 3.4 删除照片
echo -e "\n[步骤 3.4] 删除照片..."
RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/v1/albums/photos/1" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: DELETE /api/v1/albums/photos/1"
echo "响应: $RESPONSE"

# 4. 智能体流程
echo ""
echo "=== 4. 智能体流程测试 ==="

# 4.1 获取智能体状态
echo -e "\n[步骤 4.1] 获取智能体状态..."
RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/agents/status" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: GET /api/v1/agents/status"
echo "响应: $RESPONSE"

# 4.2 运行测试智能体
echo -e "\n[步骤 4.2] 运行测试智能体..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/agents/test/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"test_type":"unit","target":"test.py"}')
echo "请求: POST /api/v1/agents/test/run"
echo "响应: $RESPONSE"

# 4.3 创建智能体任务
echo -e "\n[步骤 4.3] 创建智能体任务..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/agents/tasks" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"agent_type":"test","task":"run unit tests","input_data":{}}')
echo "请求: POST /api/v1/agents/tasks"
echo "响应: $RESPONSE"

# 4.4 列出任务
echo -e "\n[步骤 4.4] 列出任务..."
RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/agents/tasks" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: GET /api/v1/agents/tasks"
echo "响应: $RESPONSE"

echo ""
echo "========================================"
echo "测试完成"
echo "========================================"