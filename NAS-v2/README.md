# TrueNAS-Style 私有 NAS 系统

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                         NAS 系统                            │
├─────────────────────────────────────────────────────────────┤
│  UI 层 (Vue3 + Bootstrap)                                   │
├─────────────────────────────────────────────────────────────┤
│  API 层 (FastAPI)                                           │
│  ├── /api/v1/storage    - 存储管理                          │
│  ├── /api/v1/share     - 共享服务 (SMB/NFS)                 │
│  ├── /api/v1/snapshot - 快照管理                           │
│  └── /api/v1/security  - 安全认证                           │
├─────────────────────────────────────────────────────────────┤
│  核心服务层 (Python)                                         │
│  ├── storage/zfs.py     - ZFS 池/数据集管理                 │
│  ├── storage/disk.py   - 磁盘管理                           │
│  ├── share/smb.py      - SMB/CIFS 共享                     │
│  ├── share/nfs.py      - NFS 共享                          │
│  ├── share/snapshot.py - ZFS 快照                         │
│  └── security/auth.py  - 认证/授权                         │
├─────────────────────────────────────────────────────────────┤
│  系统层 (Linux)                                              │
│  ├── ZFS on Linux                                           │
│  ├── Samba (smbd)                                           │
│  ├── NFS (nfsd)                                             │
│  └── Linux PAM                                              │
└─────────────────────────────────────────────────────────────┘
```

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