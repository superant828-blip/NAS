# 长期记忆

## 2026-04-20 初始化

- 名字：小爱
- 人类：IT哥（广东）
- 钉钉：已配置成功 (dingtalk 通道)

---

## 2026-04-09 备份学习

### Claude Code 源码学习

**位置**: ~/.openclaw/workspace/claude-code-source-code/

**核心架构**:
- CLI → REPL → Query Engine → Tools → Services
- 43个内置工具（文件/执行/任务/Agent/MCP/Web）
- 88+ 斜杠命令
- Feature Flag 条件编译 (Bun feature())

**关键设计模式**:
1. **工具基类**: 统一 Tool 抽象 + JSON Schema
2. **并行预取**: MDM + Keychain 并行读取优化首屏
3. **Token 预算**: Turn-level 管理防止溢出
4. **条件编译**: feature('X') ? require() : null (108模块 DCE)

**隐藏功能**:
- KAIROS: 7×24小时自主代理模式
- BUDDY: AI 宠物系统
- Auto Dream: 后台记忆整合

**可复用经验**:
- 分层解耦架构
- 工具驱动 + 权限内置
- 增量压缩 (AutoCompact)
- 权限分级: Auto/Ask/Bypass/Deny

### 已掌握的技能

| 技能 | 功能 | 位置 |
|------|------|------|
| baidu-web-search | 百度搜索 | ~/.openclaw/workspace/skills/ |
| frontend-agent | 前端开发智能体 | ~/.openclaw/workspace/skills/ |
| minimax-web-search | MiniMax 搜索 | ~/.openclaw/workspace/skills/ |
| multi-search | 多引擎搜索 | ~/.openclaw/workspace/skills/ |
| ppt-generator | PPT 生成 | ~/.openclaw/workspace/skills/ |
| ppt-generator-pc | PPT 生成 (PC版) | ~/.openclaw/workspace/skills/ |
| tech-news-direct | 科技资讯 | ~/.openclaw/workspace/skills/ |
| Skill-Vetter | 技能审查 | ~/.openclaw/workspace/skills/ |
| web-learner | 自主上网学习 | ~/.openclaw/workspace/skills/ |
| dingtalk-push | 钉钉消息推送 | ~/.openclaw/workspace/skills/ |

### 源码学习

| 项目 | 位置 | 说明 |
|------|------|------|
| Claude Code 源码 | ~/.openclaw/workspace/claude-code-source-code/ | v2.1.88 完整源码 |
| AI 自动化逻辑 | claude-code-source-code/AI_AUTOMATION_LOGIC.md | 工具编排核心 |
| 研究报告 | claude-code-source-code/RESEARCH_REPORT.md | 架构深度分析 |

## 2026-04-20 深入学习

### 代码架构分析技能

**新建技能**: `skills/code-architect/`

**核心能力**:
1. 源码结构分析 - 识别入口/核心/工具/服务层
2. 架构模式提取 - Factory/Observer/Strategy 等
3. Agent 循环理解 - 输入→API→工具执行→循环
4. 工具系统分析 - 接口/分类/权限/渲染
5. 渐进式机制识别 - 12层生产级扩展
6. Feature Flag 分析 - DCE/灰度/内外差异

**分析维度**:
- 代码规模 (文件数/行数)
- 架构分层 (入口→引擎→工具→服务→状态)
- 数据流 (输入处理/API调用/工具执行/状态)
- 扩展性 (插件/命令/工具/MCP)

**参考资源**:
- `skills/code-architect/SKILL.md` - 技能定义
- `skills/code-architect/references/claude-code-architecture.md` - 架构笔记
- `claude-code-source-code/README.md` - 完整分析 (800+ 行)

### Hermes Model Bridge

**新建程序**: `hermes-bridge/`

**功能**: 将 OpenClaw 配置的模型分享给 Hermes Agent 使用

**两种模式**:
1. **MCP 模式** - 作为 MCP 工具供 Hermes 调用
2. **API 模式** - 提供 OpenAI 兼容的 HTTP API

**核心文件**:
- `hermes-model-bridge.js` - 主程序
- `README.md` - 使用说明

**启动方式**:
```bash
cd hermes-bridge
node hermes-model-bridge.js mcp   # MCP 模式
node hermes-model-bridge.js api    # API 模式
```

**配置**:
- 模型: qwen/MiniMax-M2.5
- API: 阿里云 DashScope
- 端口: 3456

### NAS-v2 私有云系统

**位置**: ~/.openclaw/workspace/NAS-v2/

**版本**: v3.0.0 (智能体系统版本)

**架构**:
- UI层: Vue3 + Bootstrap
- API层: FastAPI
- 智能体层: TestAgent/CodingAgent/TuningAgent
- 工具系统: 文件/Shell/ZFS/任务
- 权限引擎: 4级权限

**启动**: `./start.sh` (端口 8003)

**测试账号**: admin@nas.local / admin123

**功能**:
- 文件管理 (上传/下载/文件夹)
- ZFS存储池和数据集
- SMB/NFS共享
- 相册管理
- 分享链接
- 用户管理
- 回收站
- 智能体系统 (测试/编程/调优)

### 项目经验

- **NAS-v2 私有云系统** - 完整的文件管理、ZFS存储、相册、分享系统
- **AI Agent 系统开发** - 多智能体架构、权限引擎、任务管理
- **Claude Code 源码分析** - Hooks 架构、MCP 协议、提示词工程

### 开发规范

1. 每次修复后立即 commit + push
2. 使用 curl 测试 API
3. 多端验证（桌面 + 移动）
4. 问题用子代理并行分析
