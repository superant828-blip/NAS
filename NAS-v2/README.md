# TrueNAS-Style 私有 NAS 系统

## 版本: v3.0.0 (智能体系统版本)

> 基于 Claude Code 源码架构，集成了 AI 智能体系统

## 架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NAS 系统 v3.0.0                             │
├─────────────────────────────────────────────────────────────────────┤
│  UI 层 (Vue3 + Bootstrap)                                           │
├─────────────────────────────────────────────────────────────────────┤
│  API 层 (FastAPI)                                                   │
│  ├── /api/v1/storage    - 存储管理                                    │
│  ├── /api/v1/share     - 共享服务 (SMB/NFS)                           │
│  ├── /api/v1/snapshot  - 快照管理                                     │
│  ├── /api/v1/security  - 安全认证                                    │
│  └── /api/v1/agents   - 智能体系统 ★ NEW!                            │
├─────────────────────────────────────────────────────────────────────┤
│  智能体层 (Claude Code架构)              ★ NEW!                     │
│  ├── TestAgent       - 测试智能体 (单元/集成/API/回归测试)            │
│  ├── CodingAgent    - 编程智能体 (生成/重构/修复/审查)                │
│  ├── TuningAgent    - 性能调优智能体 (数据库/缓存/API)                │
│  └── Coordinator    - 多智能体协调器 (并行/串行/层级)                  │
├─────────────────────────────────────────────────────────────────────┤
│  工具系统                              ★ NEW!                       │
│  ├── 文件工具 (file_read/write/edit/delete/list)                    │
│  ├── Shell 工具 (安全命令执行+危险检测)                                │
│  ├── ZFS 工具 (池管理/快照)                                          │
│  └── 任务工具 (异步任务管理+进度跟踪)                                  │
├─────────────────────────────────────────────────────────────────────┤
│  权限引擎 (4级权限) + 事件系统            ★ NEW!                     │
├─────────────────────────────────────────────────────────────────────┤
│  核心服务层 (Python)                                                 │
│  ├── storage/zfs.py     - ZFS 池/数据集管理                          │
│  ├── storage/disk.py   - 磁盘管理                                    │
│  ├── share/smb.py      - SMB/CIFS 共享                             │
│  ├── share/nfs.py      - NFS 共享                                  │
│  ├── share/snapshot.py - ZFS 快照                                  │
│  └── security/auth.py  - 认证/授权                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## v3.0.0 新增功能

### 智能体系统
- **TestAgent**: 自动化测试生成与执行 (单元/集成/API/回归/冒烟)
- **CodingAgent**: 代码生成/重构/Bug修复/代码审查/性能优化
- **TuningAgent**: 数据库/缓存/API/配置性能调优
- **AgentCoordinator**: 多智能体协调 (并行/串行/层级模式)

### 工具系统
- 11个内置工具: 文件操作、Shell执行、ZFS管理、任务管理
- 统一工具基类 (参考 Claude Code Tool.ts)
- 权限内置于工具层

### 权限引擎
- 4级权限模式: Auto/Ask/Bypass/Deny
- 危险操作检测 (命令/文件/路径)
- 规则引擎

### 事件系统
- 事件驱动架构
- 任务状态变更通知
- 可扩展事件处理器

## 核心功能

1. **存储管理**
   - ZFS 池创建/导入/导出
   - 数据集管理
   - 磁盘健康监测

2. **共享服务**
   - SMB/CIFS 共享 (Windows/macOS)
   - NFS 共享 (Linux)

3. **快照管理**
   - 手动快照
   - 自动快照计划
   - 快照还原

4. **安全特性**
   - 用户/组认证 (PAM)
   - 访问控制列表 (ACL)
   - 加密存储

## API 接口

### 存储
- `GET /api/v1/storage/pools` - 列出所有池
- `POST /api/v1/storage/pools` - 创建池
- `GET /api/v1/storage/pools/{name}` - 池详情
- `DELETE /api/v1/storage/pools/{name}` - 删除池
- `GET /api/v1/storage/datasets` - 数据集列表
- `POST /api/v1/storage/datasets` - 创建数据集

### 共享
- `GET /api/v1/shares` - 共享列表
- `POST /api/v1/shares/smb` - 创建 SMB 共享
- `POST /api/v1/shares/nfs` - 创建 NFS 共享
- `DELETE /api/v1/shares/{id}` - 删除共享

### 快照
- `GET /api/v1/snapshots` - 快照列表
- `POST /api/v1/snapshots` - 创建快照
- `POST /api/v1/snapshots/{id}/rollback` - 回滚快照
- `DELETE /api/v1/snapshots/{id}` - 删除快照

### 用户
- `POST /api/v1/auth/login` - 登录
- `GET /api/v1/users` - 用户列表
- `POST /api/v1/users` - 创建用户

### 智能体 (v3.0.0 新增)
- `POST /api/v1/agents/tasks` - 创建智能体任务
- `GET /api/v1/agents/tasks/{id}` - 获取任务状态
- `POST /api/v1/agents/test/run` - 运行测试
- `POST /api/v1/agents/coding/run` - 运行编程
- `POST /api/v1/agents/tuning/run` - 运行调优
- `GET /api/v1/agents/status` - 系统状态
- `POST /api/v1/agents/pipeline/test-and-fix` - CI/CD 流水线

## 快速开始

```bash
# 启动服务
cd NAS-v2
./start.sh

# 访问
# Web: http://localhost:8000
# API: http://localhost:8000/docs
```

默认账号: `admin` / `admin123`

## GitHub

- 仓库: https://github.com/superant828-blip/NAS
- 版本: v3.0.0 (智能体系统版本)
- 基于 Claude Code 源码架构设计