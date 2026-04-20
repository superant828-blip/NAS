# NAS-v2 端到端集成测试计划

## 项目信息
- **项目位置**: /home/test/.openclaw/workspace/NAS-v2
- **后端地址**: http://localhost:8000
- **测试账号**: admin@nas.local / admin123

---

## 测试流程记录

> ⚠️ **注意**: 由于当前环境的 exec 工具被安全策略限制，无法直接执行 curl 命令。已创建以下测试脚本：
> - `integration_test.sh` - Bash curl 脚本
> - `test_api.py` - Python requests 脚本  
> - `TEST_README.md` - 使用说明

---

## 1. 完整用户流程

### 1.1 用户登录
- **请求**: `POST /api/v1/auth/login`
- **参数**: `{"email":"admin@nas.local","password":"admin123"}`
- **预期响应**: 包含 access_token 的 JSON

### 1.2 获取用户信息
- **请求**: `GET /api/v1/auth/me`
- **Headers**: `Authorization: Bearer {TOKEN}`
- **预期响应**: 用户信息

### 1.3 获取文件列表
- **请求**: `GET /api/v1/files/`
- **Headers**: `Authorization: Bearer {TOKEN}`
- **预期响应**: 文件列表 JSON

### 1.4 创建文件夹
- **请求**: `POST /api/v1/files/folder`
- **Headers**: `Authorization: Bearer {TOKEN}`
- **参数**: `{"name":"test_folder","parent_id":null}`
- **预期响应**: 新建文件夹信息

### 1.5 上传文件
- **请求**: `POST /api/v1/files/upload`
- **Headers**: `Authorization: Bearer {TOKEN}`
- **Form Data**: `file={file_content}`
- **预期响应**: 上传文件信息

### 1.6 获取分享链接
- **请求**: `GET /api/v1/share/links`
- **Headers**: `Authorization: Bearer {TOKEN}`
- **预期响应**: 分享链接列表

---

## 2. 文件管理流程

### 2.1 创建文件夹
- **请求**: `POST /api/v1/files/folder`
- **参数**: `{"name":"folder_for_test","parent_id":null}`

### 2.2 移动文件
- **请求**: `POST /api/v1/files/move`
- **参数**: `{"file_id":1,"new_parent_id":1}`

### 2.3 删除文件
- **请求**: `DELETE /api/v1/files/{file_id}`

### 2.4 获取回收站
- **请求**: `GET /api/v1/trash/`

---

## 3. 相册流程

### 3.1 创建相册
- **请求**: `POST /api/v1/albums`
- **参数**: `{"name":"test_album","description":"test"}`

### 3.2 获取相册列表
- **请求**: `GET /api/v1/albums`

### 3.3 上传照片
- **请求**: `POST /api/v1/albums/{album_id}/photos`
- **Form Data**: `photo={image_file}`

### 3.4 查看相册照片
- **请求**: `GET /api/v1/albums/{album_id}/photos`

### 3.5 删除照片
- **请求**: `DELETE /api/v1/albums/photos/{photo_id}`

---

## 4. 智能体流程

### 4.1 获取智能体状态
- **请求**: `GET /api/v1/agents/status`
- **Headers**: `Authorization: Bearer {TOKEN}`
- **预期响应**: 
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

### 4.2 运行测试智能体
- **请求**: `POST /api/v1/agents/test/run`
- **参数**: `{"test_type":"unit","target":"test.py"}`

### 4.3 创建智能体任务
- **请求**: `POST /api/v1/agents/tasks`
- **参数**: 
```json
{
  "agent_type": "test",
  "task": "run unit tests",
  "input_data": {},
  "mode": "parallel"
}
```

### 4.4 列出任务
- **请求**: `GET /api/v1/agents/tasks`

### 4.5 获取任务状态
- **请求**: `GET /api/v1/agents/tasks/{task_id}`

---

## 执行命令示例

### 使用 curl (需要后端运行)

```bash
# 1. 登录获取Token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nas.local","password":"admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

# 2. 使用Token访问API
curl -X GET http://localhost:8000/api/v1/files/ \
  -H "Authorization: Bearer $TOKEN"

# 3. 获取智能体状态
curl -X GET http://localhost:8000/api/v1/agents/status \
  -H "Authorization: Bearer $TOKEN"
```

### 使用 Python 脚本

```bash
cd /home/test/.openclaw/workspace/NAS-v2
pip install requests
python3 test_api.py
```

---

## 测试结果记录模板

| 步骤 | API | 请求 | 响应状态码 | 结果 |
|------|-----|------|------------|------|
| 1.1 | POST /auth/login | {"email":"...","password":"..."} | 200 | ✓/✗ |
| 1.2 | GET /auth/me | Headers: Bearer {token} | 200 | ✓/✗ |
| ... | ... | ... | ... | ... |

---

## 文件清单

- `integration_test.sh` - Bash 测试脚本
- `test_api.py` - Python 测试脚本  
- `TEST_README.md` - 快速开始指南
- `TEST_PLAN.md` - 本测试计划文档