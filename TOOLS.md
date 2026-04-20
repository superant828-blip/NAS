# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## 代码架构分析 (Code Architect)

### 源码位置

- Claude Code: `~/workspace/claude-code-source-code/`
- 文档: `claude-code-source-code/docs/zh/`
- 核心文件: `src/query.ts`, `src/main.tsx`, `src/Tool.ts`

### 架构分析方法

1. **目录结构分析** - 识别入口/核心/工具/服务
2. **入口点定位** - main.tsx, index.ts, cli.ts
3. **核心循环提取** - 找到 Agent Loop
4. **工具系统分析** - 工具接口、注册、权限
5. **状态管理识别** - Redux/Context/Zustand
6. **设计模式总结** - Factory/Observer/Strategy

### 学习资源

- `skills/code-architect/` - 代码架构分析技能
- `claude-code-source-code/README.md` - 完整架构文档
- `claude-code-source-code/docs/zh/` - 中文分析报告

---

Add whatever helps you do your job. This is your cheat sheet.
