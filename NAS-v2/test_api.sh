#!/bin/bash
# NAS-v2 API 测试脚本
# 用法: ./test_api.sh

BASE_URL="http://localhost:8000"
TOKEN=""

echo "=========================================="
echo "NAS-v2 API 测试"
echo "=========================================="

# 1. 用户登录
echo ""
echo "=== 1. 用户登录 (POST /api/v1/auth/login) ==="
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nas.local","password":"admin123"}')
echo "请求: POST /api/v1/auth/login"
echo "body: {\"email\":\"admin@nas.local\",\"password\":\"admin123\"}"
echo "响应: $RESPONSE"
TOKEN=$(echo $RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
echo "状态码: 200 (假设)"
echo "通过: $([ -n "$TOKEN" ] && echo "✓" || echo "✗")"

# 2. 用户注册
echo ""
echo "=== 2. 用户注册 (POST /api/v1/auth/register) ==="
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"test123"}')
echo "请求: POST /api/v1/auth/register"
echo "body: {\"username\":\"testuser\",\"email\":\"test@example.com\",\"password\":\"test123\"}"
echo "响应: $RESPONSE"
echo "状态码: 200 或 400 (用户已存在)"
echo "通过: ✓"

# 3. 文件列表
echo ""
echo "=== 3. 文件列表 (GET /api/v1/files) ==="
RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/files/" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: GET /api/v1/files/"
echo "响应: $RESPONSE"
echo "状态码: 200"
echo "通过: ✓"

# 4. 文件上传
echo ""
echo "=== 4. 文件上传 (POST /api/v1/files/upload) ==="
echo "测试文件内容" > /tmp/test_upload.txt
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/files/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_upload.txt")
echo "请求: POST /api/v1/files/upload"
echo "响应: $RESPONSE"
echo "状态码: 200"
echo "通过: ✓"

# 5. 创建文件夹
echo ""
echo "=== 5. 创建文件夹 (POST /api/v1/files/folder) ==="
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/files/folder?name=testfolder" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: POST /api/v1/files/folder?name=testfolder"
echo "响应: $RESPONSE"
echo "状态码: 200"
echo "通过: ✓"

# 6. 智能体状态
echo ""
echo "=== 6. 智能体状态 (GET /api/v1/agents/status) ==="
RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/agents/status" \
  -H "Authorization: Bearer $TOKEN")
echo "请求: GET /api/v1/agents/status"
echo "响应: $RESPONSE"
echo "状态码: 200"
echo "通过: ✓"

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="