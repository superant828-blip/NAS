# NAS-v2 端到端集成测试说明

## 概述
本目录包含用于测试 NAS-v2 项目的集成测试脚本。

## 测试脚本

### 1. Bash 脚本 (需要 curl)
```bash
bash integration_test.sh
```

### 2. Python 脚本 (需要 requests 库)
```bash
# 安装依赖
pip install requests

# 运行测试
python3 test_api.py
```

## 测试流程

### 1. 完整用户流程
- [x] 用户登录 (POST /api/v1/auth/login)
- [x] 获取用户信息 (GET /api/v1/auth/me)
- [x] 获取文件列表 (GET /api/v1/files/)
- [x] 创建文件夹 (POST /api/v1/files/folder)
- [x] 上传文件 (POST /api/v1/files/upload)
- [x] 获取分享链接 (GET /api/v1/share/links)

### 2. 文件管理流程
- [x] 创建文件夹
- [x] 移动文件 (POST /api/v1/files/move)
- [x] 删除文件 (DELETE /api/v1/files/{id})
- [x] 获取回收站 (GET /api/v1/trash/)

### 3. 相册流程
- [x] 创建相册 (POST /api/v1/albums)
- [x] 获取相册列表 (GET /api/v1/albums)
- [x] 上传照片 (POST /api/v1/albums/{id}/photos)
- [x] 获取相册照片 (GET /api/v1/albums/{id}/photos)

### 4. 智能体流程
- [x] 获取状态 (GET /api/v1/agents/status)
- [x] 运行测试 (POST /api/v1/agents/test/run)
- [x] 创建任务 (POST /api/v1/agents/tasks)
- [x] 列出任务 (GET /api/v1/agents/tasks)

## 手动测试命令

### 登录测试
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nas.local","password":"admin123"}'
```

### 获取文件列表
```bash
curl -X GET http://localhost:8000/api/v1/files/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 获取智能体状态
```bash
curl -X GET http://localhost:8000/api/v1/agents/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 预期响应示例

### 登录成功
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@nas.local",
    "role": "admin"
  }
}
```

### 智能体状态
```json
{
  "stats": {
    "total_tasks": 0,
    "running_tasks": 0,
    "completed_tasks": 0,
    "failed_tasks": 0
  },
  "workers": [],
  "tasks": []
}
```

## 故障排除

### 401 未授权
- 检查Token是否正确传递
- 检查Token是否过期

### 500 服务器错误
- 检查后端日志: `tail -50 /tmp/nas-v2.log`
- 检查Python依赖是否安装

### 连接拒绝
- 确认后端服务正在运行
- 检查端口8000是否被占用