# Claude Code 架构参考笔记

> 来源: Claude Code v2.1.88 源码分析
> 日期: 2026-04-20

## 核心数据

| 指标 | 数值 |
|------|------|
| 源文件 (.ts/.tsx) | ~1,884 |
| 代码行数 | ~512,664 |
| 最大单文件 | query.ts (1729行) |
| 内置工具 | 40+ |
| 斜杠命令 | 80+ |
| 依赖包 | 192 |

## 四层架构

```
入口层 (main.tsx)
    ↓
查询引擎层 (query.ts)
    ↓
┌────────────┬────────────┬───────────┐
│ 工具系统   │  服务层    │  状态层   │
│ Tool.ts    │ api/claude │ AppState  │
│ 40+ tools  │ compact/   │ Context   │
│            │ mcp/       │           │
└────────────┴────────────┴───────────┘
```

## Agent 循环 (query.ts)

```typescript
while (true) {
  // 1. 获取系统提示
  fetchSystemPromptParts()

  // 2. 规范化消息
  normalizeMessagesForAPI()

  // 3. 调用 Claude API (流式)
  const response = await claude.messages.create({
    model: 'claude-sonnet-4-20250514',
    messages: messages,
    tools: toolDefinitions,
    system: systemPrompt
  })

  // 4. 处理响应
  for await (const event of response) {
    if (event.type === 'content_block_delta') {
      // 文本或工具调用
    }
  }

  // 5. 工具执行循环
  if (stop_reason === 'tool_use') {
    await executeTools()
    continue // 循环
  }

  // 6. 返回结果
  return result
}
```

## 工具接口 (Tool.ts)

```typescript
interface Tool<Input, Output, Progress> {
  // 生命周期
  validateInput(input: Input): ValidationResult
  checkPermissions(context: ToolUseContext): Promise<PermissionResult>
  call(input: Input): Promise<Output>

  // 能力标识
  isEnabled(): boolean
  isConcurrencySafe(): boolean
  isReadOnly(): boolean
  isDestructive(): boolean

  // 渲染 (React/Ink)
  renderToolUseMessage(): JSX.Element
  renderToolResultMessage(): JSX.Element
  renderToolUseProgressMessage(): JSX.Element

  // AI 面
  prompt(): string
  description(): string
}
```

## 12 渐进式机制

| # | 机制 | 文件 |
|---|------|------|
| 1 | 基础循环 | query.ts |
| 2 | 工具调度 | Tool.ts |
| 3 | 规划模式 | EnterPlanModeTool |
| 4 | 子代理 | AgentTool |
| 5 | Skill 按需 | SkillTool |
| 6 | 上下文压缩 | services/compact/ |
| 7 | 持久任务 | TaskCreateTool |
| 8 | 后台任务 | DreamTask |
| 9 | Agent 团队 | TeamCreateTool |
| 10 | 团队协议 | SendMessageTool |
| 11 | 协调器 | coordinatorMode.ts |
| 12 | Worktree | EnterWorktreeTool |

## Feature Flag 模式

```typescript
// Bun 编译时 intrinsics
const isEnabled = feature('FEATURE_NAME')

// 编译时 vs 运行时
if (feature('KAIROS')) {
  // 打包时保留
} else {
  // 打包时删除 (DCE)
}

// 运行时检查
if (process.env.USER_TYPE === 'ant') {
  // 内部版功能
}
```

## 上下文压缩策略

1. **autoCompact** - 超阈值时自动摘要
2. **snipCompact** - 修剪僵尸消息
3. **contextCollapse** - 上下文重构

## MCP 集成架构

```
MCPConnectionManager
├── Server Discovery (settings.json)
├── Transport (stdio/http/ws/sdk)
├── Lifecycle (connect → initialize → list_tools)
├── Auth (OAuth 2.0, XAA)
└── Tool Registration (mcp__<server>__<tool>)
```

## 权限系统流程

```
请求 → validateInput → Hooks → 规则匹配
                                      ↓
                              无匹配?
                                      ↓
                              ┌───────┴───────┐
                              ↓               ↓
                         交互提示        alwaysAllow/alwaysDeny
                              ↓
                        权限检查 → 执行
```

## 关键设计模式

| 模式 | 实现 |
|------|------|
| AsyncGenerator 流式 | QueryEngine.query() |
| Builder + Factory | buildTool() |
| Branded Types | AgentId, SessionId |
| Discriminated Unions | Message { type: 'user' \| 'assistant' } |
| Observer + StateMachine | StreamingToolExecutor |
| Snapshot State | FileHistoryState |
| Ring Buffer | Error log |
| Fire-and-Forget | recordTranscript() |
| Lazy Schema | lazySchema() |
| Context Isolation | AsyncLocalStorage |

## 未公开功能 (Feature Flag 后)

- **KAIROS** - 自主代理模式
- **VOICE_MODE** - 语音输入
- **WEB_BROWSER_TOOL** - 浏览器自动化
- **COORDINATOR_MODE** - 多代理协调
- **WORKFLOW_SCRIPTS** - 工作流脚本
- **BUDDY** - 虚拟宠物系统
- **CONTEXT_COLLAPSE** - 上下文折叠

## 未来方向

1. **Numbat** - 下一代模型
2. **Opus 4.7 / Sonnet 4.8** - 新版本
3. **KAIROS** - 无人值守运行
4. **语音模式** - Push-to-talk
5. **多代理协调** - Team + Coordinator
