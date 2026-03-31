# 长期记忆

## 自我进化学习 (2026-04-01 深入研究)

### 一、深入研究：Hooks 架构

#### 1. 权限核心 Hook: useCanUseTool

```typescript
// useCanUseTool.tsx - 权限检查核心
function useCanUseTool(setToolUseConfirmQueue, setToolPermissionContext) {
  return async function canUseTool(tool, input, toolUseContext, ...): Promise<PermissionDecision> {
    // 1. 创建权限上下文
    const ctx = createPermissionContext(...)
    
    // 2. 强制决策（测试/自动模式）
    if (forceDecision) return forceDecision
    
    // 3. 权限检查
    const result = await hasPermissionsToUseTool(tool, input, ...)
    
    // 4. 根据行为处理
    switch (result.behavior) {
      case "allow": resolve(allow); break;
      case "deny": resolve(deny); break;
      case "ask": 
        // 5. 询问用户
        const coordinatorDecision = await handleCoordinatorPermission(...)
        const interactiveDecision = await handleInteractivePermission(...)
        break;
    }
  }
}
```

#### 2. 关键 Hooks (80+ 个)

| 类别 | 示例 | 功能 |
|------|------|------|
| **权限** | useCanUseTool | 工具使用权限检查 |
| **输入** | useTextInput, useArrowKeyHistory | 文本输入处理 |
| **会话** | useSessionBackgrounding, useRemoteSession | 会话管理 |
| **IDE** | useIdeConnectionStatus, useDiffInIDE | IDE集成 |
| **权限** | useClipboardImageHint, useChromeExtensionNotification | 扩展集成 |
| **任务** | useTaskListWatcher, useTasksV2 | 任务列表 |

#### 3. Hooks 设计模式

- **条件编译**: `feature('X') ? require(...) : null`
- **上下文创建**: `createPermissionContext()`
- **决策委派**: `handleCoordinatorPermission()` / `handleInteractivePermission()`

---

### 二、深入研究：MCP (Model Context Protocol)

#### 1. MCP 客户端架构

```typescript
// client.ts - MCP 客户端核心
class McpClient {
  async connect(serverConfig: McpServerConfig): Promise<MCPServerConnection> {
    // 支持三种传输方式
    const transport = serverConfig.type === 'stdio'
      ? new StdioClientTransport(command)
      : serverConfig.type === 'sse'
      ? new SSEClientTransport(url)
      : new StreamableHTTPClientTransport(url)
    
    // 初始化连接
    await transport.initialize()
    
    // 获取工具列表
    const tools = await transport.listTools()
    return { transport, tools: normalizeMcpTools(tools) }
  }
  
  async callTool(name: string, input: unknown): Promise<ToolResult> {
    const result = await this.transport.callTool(name, input)
    return normalizeMcpResult(result)
  }
}
```

#### 2. MCP 工具类型

- **stdio**: 本地命令 (如文件系统)
- **sse**: Server-Sent Events
- **streamable-http**: HTTP 流式传输

---

### 三、深入研究：系统提示词工程

#### 1. 模块化提示词

```typescript
// systemPromptSections.ts - 提示词分段
export function systemPromptSection(name: string, compute: ComputeFn) {
  return { name, compute, cacheBreak: false }  // 可缓存
}

export function DANGEROUS_uncachedSystemPromptSection(name, compute, reason) {
  return { name, compute, cacheBreak: true }  // 不缓存
}

// 使用示例
const sections = [
  systemPromptSection("os", computeOS),
  systemPromptSection("git", computeGitStatus),
  systemPromptSection("mcp", computeMcpTools),
]
```

#### 2. 提示词缓存策略

- **缓存命中**: 减少 Token 消耗
- **缓存失效**: `/clear` 或 `/compact` 时清除
- **动态段**: 每轮重新计算 (cacheBreak=true)

---

### 四、深入研究：上下文管理

#### 1. Git 上下文

```typescript
// context.ts - Git 状态注入
export const getGitStatus = memoize(async (): Promise<string | null> => {
  const [branch, mainBranch, status, log, userName] = await Promise.all([
    getBranch(),
    getDefaultBranch(),
    execFileNoThrow(gitExe(), ['status', '--short']),
    execFileNoThrow(gitExe(), ['log', '--oneline', '-n', '5']),
    execFileNoThrow(gitExe(), ['config', 'user.name']),
  ])
  
  return `Current branch: ${branch}\nMain branch: ${mainBranch}\n${status}`
})
```

#### 2. 上下文包含内容

- Git 状态 (分支、状态、日志)
- 项目结构
- MCP 服务器信息
- 用户设置
- 内存文件 (Claude.md)

---

### 五、深入研究：错误处理

#### 1. API 错误分类

```typescript
// errors.ts - 错误处理
export async function handleApiError(error: APIError) {
  switch (error.type) {
    case 'rate_limit_error':
      return handleRateLimit(error)
    case 'authentication_error':
      return handleAuthError(error)
    case 'invalid_request_error':
      return handleInvalidRequest(error)
    case 'server_error':
      return handleServerError(error)
    case 'connection_error':
      return handleConnectionError(error)
  }
}
```

#### 2. 重试机制

```typescript
// withRetry.ts - 重试逻辑
async function withRetry(fn, options = {}) {
  const { maxRetries = 3, backoff = 'exponential' } = options
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      if (!isRetryable(error)) throw error
      const delay = backoff === 'exponential' 
        ? Math.pow(2, attempt) * 1000 
        : 1000
      await sleep(delay)
    }
  }
}
```

---

### 六、深入研究：MCP 服务集成

#### 1. 服务发现与连接

```typescript
// client.ts - MCP 连接管理
class MCPConnectionManager {
  private connections: Map<string, MCPServerConnection>
  
  async connectAll(config: McpConfig[]): Promise<void> {
    await Promise.all(
      config.map(async (server) => {
        const connection = await this.connect(server)
        this.connections.set(server.name, connection)
      })
    )
  }
  
  getTools(): Tools {
    return this.connections.flatMap(c => c.tools)
  }
}
```

#### 2. OAuth 认证

```typescript
// auth.ts - MCP OAuth
async function handleOAuth(server: McpServerConfig): Promise<void> {
  const authUrl = buildOAuthUrl(server.auth)
  const code = await openBrowser(authUrl)
  const tokens = await exchangeCode(code)
  saveTokens(server.name, tokens)
}
```

---

## 自我进化总结 (2026-04-01)

### 新增核心能力

1. **Hooks 驱动架构** - 80+ 个Hooks支撑复杂交互
2. **MCP 协议集成** - 标准化的工具扩展协议
3. **提示词模块化** - 可缓存的分段式系统提示
4. **智能上下文** - Git/项目/会话状态自动注入
5. **错误恢复** - 多级重试 + 分类处理

### 可复用的架构

```typescript
// 1. 模块化提示词
const sections = [
  systemPromptSection("git", computeGit),
  systemPromptSection("mcp", computeMcp),
]

// 2. Hooks 权限模式
async function useToolPermission(tool, input, context) {
  const decision = await checkPermissions(tool, input)
  return decision.behavior === "allow" ? allow : prompt()
}

// 3. MCP 连接池
class MCPManager {
  async connectAll(servers: Config[]) { ... }
  getTools() { return flatMap(tools) }
}
```

---

### 下一步学习方向

1. **多模态** - 图像/音频处理
2. **持久化** - 会话状态管理
3. **协作** - 多用户/多会话
4. **插件系统** - 动态扩展

---

## Claude Code 源码分析与智能体系统开发 (2026-04-01)

### 一、Claude Code 源码分析

#### 1. 整体架构 (来自源码分析)

```
Claude Code (v2.1.88)
├── CLI 入口 (main.tsx, 804KB)
├── REPL 交互层 (ink + React)
├── 查询引擎 (query.ts, 68KB)
│   ├── 消息构建 → API调用 → 流式处理 → 工具编排
│   └── 上下文压缩 → Token预算管理
├── 工具系统 (43个工具)
│   ├── 文件: FileRead/Write/Edit/Delete/Glob/Grep
│   ├── 执行: Bash/PowerShell/REPL
│   ├── 任务: TaskCreate/List/Get/Update/Stop
│   ├── Agent: AgentTool (多代理)
│   └── MCP: MCPTool + 扩展
├── 服务层
│   ├── API / MCP / Analytics / Policy / Compact / Skills
├── 状态管理
│   └── AppState / Hooks / History / Stats
```

#### 2. 核心设计模式

| 设计模式 | 实现方式 | 价值 |
|---------|---------|------|
| **工具基类** | Tool抽象 + JSON Schema | 统一接口 + 权限内置 |
| **条件编译** | Bun feature() DCE | 按环境裁剪体积 (108模块) |
| **并行预取** | MDM + Keychain并行 | 优化首屏时间 |
| **Token预算** | Turn-level管理 | 防上下文溢出 |
| **智能并发** | 读并发 + 写串行 | 效率安全平衡 |

#### 3. 隐藏功能 (源码泄露发现)

- **KAIROS**: 7×24小时自主代理模式
- **BUDDY**: AI宠物系统
- **Undercover Mode**: 隐藏AI身份
- **模型代号**: Capybara/Numbat/Tengu

#### 4. 统计数据

- 源文件: ~1,884
- 代码行数: ~512,664
- 内置工具: 43
- 斜杠命令: 88+
- Feature Flags: 35+

---

### 二、NAS-v2 智能体系统开发

#### 1. 新增模块

| 模块 | 文件 | 功能 |
|------|------|------|
| **工具系统** | api/tools/ | 11个工具 (文件/Shell/ZFS/任务) |
| **智能体** | api/agents/ | TestAgent/CodingAgent/TuningAgent |
| **权限引擎** | api/permissions/ | 4级权限模式 |
| **任务系统** | api/jobs/ | 异步任务管理 |
| **事件系统** | api/events/ | 事件驱动 |
| **API路由** | api/routes/agents.py | 12个端点 |

#### 2. 使用方式

```python
# 测试智能体
POST /api/v1/agents/test/run?test_type=unit&target=/api/main.py

# 编程智能体
POST /api/v1/agents/coding/run?task_type=generate&target=新模块.py

# 性能调优
POST /api/v1/agents/tuning/run?target=api

# 状态查看
GET /api/v1/agents/status
```

#### 3. Git 版本

- 仓库: https://github.com/superant828-blip/NAS
- 版本: v3.0.0
- Commit: b8403cf
- 新增: 28文件, +5289行

---

### 三、经验总结

#### 1. AI 编程系统核心要素

1. **工具驱动架构** - 一切皆工具，易扩展
2. **权限分级** - Auto/Ask/Bypass/Deny
3. **智能并发** - 读并发，写串行
4. **增量压缩** - 非全量，而是摘要
5. **Token 预算** - 防止上下文溢出

#### 2. 安全设计要点

- 危险文件/目录黑名单
- 命令语义分析
- 路径遍历检测
- 只读验证
- 权限请求用户确认

#### 3. 多智能体协调模式

| 模式 | 场景 |
|------|------|
| SEQUENTIAL | 顺序执行有依赖的任务 |
| PARALLEL | 并行执行独立任务 |
| HIERARCHICAL | 主任务分配子任务 |
| BROADCAST | 广播给所有智能体 |

#### 4. 可复用的架构

```python
# 工具基类
class BaseTool(ABC):
    name: str
    input_schema: Dict
    
    async def execute(self, input_data, context) -> ToolResult:
        # 权限检查 → 验证 → 执行
        pass

# 权限引擎
class PermissionEngine:
    - 危险检测
    - 路径控制
    - 规则匹配

# 任务管理器
class JobManager:
    - 任务创建/取消
    - 并发控制
    - 进度跟踪
```

---

## 测试用例与开发经验总结 (2026-03-28)

### 一、测试用例设计体系

#### 1. 按测试层次分类

| 测试层级 | 测试内容 | 测试方法 |
|---------|---------|----------|
| 单元测试 | 后端API函数、工具类 | curl直接调用API |
| 集成测试 | 前后端交互、数据库操作 | 完整业务流程测试 |
| 系统测试 | ZFS存储、NFS/SMB共享 | 端到端功能验证 |
| 验收测试 | 用户故事（登录、上传、下载） | 人工/自动化执行 |

#### 2. 按功能模块分类

```
NAS项目功能测试矩阵
├── 用户认证
│   ├── 登录成功/失败
│   ├── Token过期处理
│   └── 多角色权限验证
├── 文件管理
│   ├── 上传（单文件/批量/大文件）
│   ├── 下载（认证/路径问题）
│   ├── 删除/移动/重命名
│   ├── 排序（名称/大小/日期/类型）
│   └── 视图模式（网格/列表/详情）
├── 存储系统
│   ├── ZFS池状态
│   ├── 数据集管理
│   └── 快照操作
├── 共享服务
│   ├── SMB配置
│   ├── NFS导出
│   └── 用户访问控制
└── 系统配置
    ├── 文件类型白名单
    ├── 告警阈值
    └── Webhook推送
```

### 二、问题根因分析模式

#### 1. 数据流问题

```
问题：下载文件返回"File not found on disk"

根因分析：
数据库记录(path=/ISO/xxx.mp4) → API读取path → 拼接UPLOAD路径 → ZFS路径不匹配

解决方案：多路径回退机制
- 主要路径：/nas-pool/data/uploads/
- 备用路径：~/NAS-v2/uploads/
```

#### 2. 前端状态问题

```
问题：排序功能点击无反应

根因：Vue 3中 select 的 @change 可能未触发

解决方案：
1. 添加显式调用 sortFiles()
2. 使用 watch 监听 sortBy 变化
3. 添加 viewMode 状态管理
```

#### 3. API路径问题

```
问题：移动端分享链接功能404

根因：前端调用/shareLinks，后端API是/api/v1/shares/links

解决：统一接口路径
```

### 三、冒烟测试（每次提交后）

```bash
# 核心功能冒烟
1. 登录API → curl测试
2. 文件列表 → curl测试  
3. 页面加载 → curl状态码
4. ZFS状态 → zpool status
```

### 四、回归测试清单

```
功能回归清单：
□ 用户登录/登出
□ 文件上传（单文件、批量、大文件）
□ 文件下载（认证、路径）
□ 文件排序（名称、大小、日期、类型）
□ 视图切换（网格、列表、详情）
□ 目录选择（ZFS数据集）
□ 用户角色权限
□ 分享链接创建/删除
□ 存储池状态显示
□ 快照管理
```

### 五、常见问题与解决方案

| 问题 | 根因 | 解决方案 |
|------|------|----------|
| 页面500错误 | 后端异常 | 检查后端日志 |
| 401未授权 | Token未传递 | 统一认证中间件 |
| 404文件不存在 | 路径配置变更 | 多路径回退机制 |
| 400参数错误 | 请求格式问题 | 接口文档对照 |
| 排序无响应 | Vue状态未绑定 | 添加watch监听 |
| 语法错误 | 代码重复定义 | 代码审查 |
| WebSocket错误 | 后端未实现 | 降级为HTTP轮询 |

### 六、开发规范

1. **API设计**：完整错误处理、参数验证、明确返回状态
2. **前端状态**：完整响应式状态、错误处理、loading状态
3. **版本管理**：每次修复立即commit+push，记录版本号
4. **多端验证**：桌面端和移动端都需要测试

### 七、常用命令

```bash
# API测试
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nas.local","password":"admin123"}'

# 检查后端
ps aux | grep "python3 api/main.py"
tail -50 /tmp/nas-v2.log

# 检查ZFS
zpool status
zfs list

# 页面检查
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
```

---

## 项目开发规范 (2026-03-27)

### NAS-v2 项目开发规范

**核心原则：**
1. **发现问题 → 多Agent分析** - 开启并行子代理分析问题，寻找解决方案
2. **快速迭代 + 版本管理** - 每次更新及时commit并推送到GitHub
3. **自主测试 + PR** - 修复后自行测试验证，然后提交PR解决问题

### 开发流程

```
发现问题
    ↓
 spawn子代理(分析问题) ← 并行Agent
    ↓
 定位根因
    ↓
 修复代码
    ↓
 本地测试API/界面
    ↓
 git commit -m "fix: xxx"
    ↓
 git push origin master
    ↓
 验证修复
```

### Git提交规范

- 使用清晰的commit信息
- 格式: `fix: 问题描述` 或 `feat: 新功能`
- 每次修复后立即提交和推送
- 保持版本历史可追溯

### 测试要点

- 后端API: 使用curl测试各端点
- 前端界面: 登录后测试各功能
- 批量操作: 文件多选、移动、删除
- 文件上传: 上传功能正常

---

## NAS私有云系统 (2026-03-26)

### 项目位置
- 位置: ~/.openclaw/workspace/NAS-v2/
- 服务地址: http://localhost:8000
- GitHub: https://github.com/superant828-blip/NAS

### 测试账号
| 账号 | 密码 | 角色 |
|------|------|------|
| admin@nas.local | admin123 | 管理员 |

### 已完成功能
- 文件管理 (上传/下载/文件夹/批量操作)
- ZFS存储池和数据集
- 相册管理
- 分享链接
- 用户管理
- 回收站

### 待完善
- 批量删除功能
- 相册照片管理
- SMB/NFS共享 (需安装服务)

### Git版本历史
- 2a015db fix: 修复文件选择和用户创建问题
- 8515015 fix: 添加返回上一级功能
- a0f86ce fix: 修复sqlite3.Row不支持get方法
- 3026f17 fix: 修复侧边栏导航点击无响应
- a9b283a fix: 修复前端初始化时undefined报错
- b0f83e6 fix: 修复ZFS数据集列表API
- 25bfd4d fix: 修复ZFS未安装时API报错500
## 2026-03-27 代码问题修复

### 已修复问题

1. **密码哈希兼容性问题** - security/auth.py
   - 原因: 新系统使用bcrypt，旧系统明文存储
   - 修复: 添加异常处理，兼容两种格式，自动升级为哈希

2. **createAlbum无错误处理** - index.html
   - 原因: 500错误时无用户提示
   - 修复: 添加res.ok检查和错误提示

3. **分享模态框文件选择** - index.html  
   - 原因: "分享选中"时selectedFiles未填充到表单
   - 修复: 添加watch监听showShareModal变化自动填充

### 已知剩余问题

- mobile.html照片上传缺少album_id传递
- 仪表盘h5结束标签错误
- 后端分享密码验证未处理异常

