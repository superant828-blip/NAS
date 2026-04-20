---
name: code-architect
version: 1.0.0
description: 代码架构分析技能 - 深度分析源代码结构、提取架构设计模式、学习并转化为自己的能力。源自对 Claude Code 源码的深度学习。
---

# Code Architect - 代码架构分析技能

## 概述

此技能赋予 AI 深度分析源代码架构的能力，源自对 Claude Code (v2.1.88) 512K 行源码的深度学习。将生产级 AI 编程助手的架构设计转化为自身能力。

## 核心能力

### 1. 源码结构分析

分析源代码目录结构，识别：
- 入口点 (entrypoints)
- 核心模块 (core)
- 工具系统 (tools)
- 命令系统 (commands)
- 服务层 (services)
- 状态管理 (state)
- 工具函数 (utils)

### 2. 架构模式提取

从源码中提取关键设计模式：

| 模式 | 应用场景 |
|------|----------|
| **AsyncGenerator 流式** | API 流式处理、工具执行 |
| **Builder + Factory** | 工具定义工厂 |
| **Branded Types** | 类型安全（防止 string/number 混淆） |
| **Feature Flag + DCE** | 编译时代码裁剪、灰度发布 |
| **Discriminated Unions** | 消息类型、状态类型 |
| **Observer + StateMachine** | 工具执行生命周期 |
| **Snapshot State** | Undo/Redo 状态快照 |
| **Lazy Loading** | 按需加载模块 |

### 3. Agent 循环理解

分析核心 Agent 循环：
```
用户输入 → 消息规范化 → API 调用 → 响应解析
                                      ↓
                              stop_reason == "tool_use"?
                                     /          \
                                   是           否
                                     ↓          ↓
                              执行工具      返回结果
                                    ↓
                              循环调用 API
```

### 4. 工具系统分析

分析工具系统的组成：
- **工具接口**: validateInput, checkPermissions, call
- **工具分类**: 文件操作、搜索、执行、Agent、交互
- **权限系统**: Hooks → 规则匹配 → 交互提示 → 执行
- **渲染层**: 工具输入/输出/进度显示

### 5. 渐进式机制分析

识别生产级系统的 12 层渐进式机制：
1. **基础循环** - Agent Loop
2. **工具调度** - Tool Dispatch
3. **规划模式** - Plan Mode
4. **子代理** - Sub-Agent
5. **Skill 按需加载** - Lazy Skill
6. **上下文压缩** - Context Compact
7. **持久化任务** - Persistent Tasks
8. **后台任务** - Background Tasks
9. **Agent 团队** - Team System
10. **团队协议** - Team Protocol
11. **协调器模式** - Coordinator
12. **资源隔离** - Worktree Isolation

### 6. Feature Flag 分析

识别代码中的 Feature Flag 机制：
- 编译时 DCE (死代码消除)
- 运行时灰度发布
- 内部版 vs 公开版差异

## 工作流

```
1. 源码探索 → 列出目录结构
2. 入口点定位 → 找到 main/index
3. 核心模块分析 → 理解数据流
4. 工具/命令分析 → 识别能力
5. 设计模式提取 → 总结架构
6. 文档化输出 → 生成分析报告
```

## 分析维度

### 代码规模
- 源文件数量
- 代码行数
- 最大单文件
- 依赖数量

### 架构分层
```
入口层 → 查询引擎层 → 工具系统层 → 服务层 → 状态层
```

### 数据流
- 用户输入处理
- API 调用链路
- 工具执行流程
- 状态管理方式

### 扩展性
- 插件系统
- 命令扩展
- 工具扩展
- MCP 集成

## 源码学习参考 (Claude Code)

### 关键文件
- `src/query.ts` (1729行) - 核心 Agent 循环
- `src/main.tsx` (4683行) - REPL 入口
- `src/Tool.ts` - 工具接口定义
- `src/tools.ts` - 工具注册
- `src/commands.ts` - 命令定义

### 目录结构
```
src/
├── main.tsx              # 入口
├── query.ts              # Agent 循环
├── Tool.ts               # 工具接口
├── tools/                # 40+ 工具
├── commands/             # 80+ 命令
├── services/             # 业务逻辑
├── state/                # 状态管理
├── utils/                # 工具函数
└── components/           # UI 组件
```

## 输出格式

生成架构分析报告，包含：
1. **数据总览** - 文件数、行数、依赖
2. **架构概览** - 分层图、数据流
3. **核心系统** - 工具、命令、权限
4. **设计模式** - 使用的模式清单
5. **扩展机制** - 插件、Feature Flag
6. **对比分析** - 与其他系统的差异

## 触发场景

1. 用户要求分析源码架构
2. 学习某项目的设计模式
3. 对比不同系统的架构差异
4. 提取可复用的架构模式
5. 将源码能力转化为自己的技能

## 注意事项

- 分析公开源码时注意版权
- 商业代码仅供学习参考
- 提取设计模式而非直接复制
- 结合自身系统特点进行转化
