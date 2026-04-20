# Hermes Model Bridge

将 OpenClaw 配置的大模型分享给 Hermes Agent 使用的桥梁程序。

## 功能

- **MCP Server 模式**: 作为 MCP 工具供 Hermes 调用
- **OpenAI 兼容 API 模式**: 提供 OpenAI 兼容的 HTTP API

## 快速开始

### 1. 安装依赖

```bash
cd hermes-bridge
npm init -y
```

### 2. 配置环境变量

```bash
# 方式一: 使用阿里云 DashScope
export DASHSCOPE_API_KEY="your-api-key"

# 方式二: 使用 OpenAI
export OPENAI_API_KEY="your-api-key"
export BASE_URL="https://api.openai.com/v1"
```

### 3. 启动服务

```bash
# MCP 模式 (供其他 MCP Client 调用)
node hermes-model-bridge.js mcp

# API 模式 (HTTP 服务)
node hermes-model-bridge.js api
```

## 配置选项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `OPENCLAW_MODEL` | qwen/MiniMax-M2.5 | 模型名称 |
| `DASHSCOPE_API_KEY` | - | API Key |
| `BASE_URL` | dashscope URL | API 基础地址 |
| `PORT` | 3456 | API 服务端口 |
| `TEMPERATURE` | 0.7 | 默认温度 |

## Hermes 集成

### 方式一: MCP 工具

在 Hermes 的 MCP 配置中添加:

```json
{
  "mcpServers": {
    "openclaw-model": {
      "command": "node",
      "args": ["/path/to/hermes-model-bridge.js", "mcp"]
    }
  }
}
```

### 方式二: HTTP API

在 Hermes 的模型配置中:

```json
{
  "provider": "openai",
  "baseUrl": "http://localhost:3456/v1",
  "apiKey": "dummy",  // 或实际 API Key
  "model": "qwen/MiniMax-M2.5"
}
```

## API 端点

启动 API 模式后可用:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/models` | GET | 列出可用模型 |
| `/v1/models/{model}` | GET | 获取模型信息 |
| `/v1/chat/completions` | POST | 对话 |

## 可用模型

默认支持以下模型 (需在 openclaw.json 中配置):

- qwen/MiniMax-M2.5
- qwen/qwen3.5-plus
- qwen/qwen3-max-2026-01-23
- qwen/qwen3-coder-next
- qwen/qwen3-coder-plus
- qwen/glm-5
- qwen/glm-4.7
- qwen/kimi-k2.5

## 使用示例

### curl 调用

```bash
curl -X POST http://localhost:3456/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy" \
  -d '{
    "model": "qwen/MiniMax-M2.5",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7
  }'
```

### 流式调用

```bash
curl -X POST http://localhost:3456/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen/MiniMax-M2.5",
    "messages": [{"role": "user", "content": "讲个故事"}],
    "stream": true
  }'
```

## 注意事项

1. 需要有效的 API Key 才能调用模型
2. API 模式默认监听 localhost，如需远程访问修改 HOST
3. MCP 模式通过 stdio 通信，需要保持进程运行
