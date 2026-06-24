# FriendAuto 项目管理文档

> 用于阶段交接，记录当前阶段关键决策、已完成部分、待办事项、重要文件修改记录和架构思路。

---

## 当前阶段：阶段 0 — 项目初始化与技术底座

### 状态：已完成

---

## 关键决策记录

| 编号 | 决策 | 选项 | 最终选择 | 原因 |
|------|------|------|----------|------|
| 1 | 数据库 | PostgreSQL / SQLite | 开发阶段用 SQLite，部署时切 PostgreSQL | 简化本地开发环境，SQLAlchemy 支持无缝切换 |
| 2 | Rust 安装失败处理 | 安装 / 跳过 | 重新安装 stable 工具链 | Tauri 必需 Rust 环境 |
| 3 | 脚本执行方式 | Tauri shell plugin / Rust Command | Rust `Command` + `invoke` | 更可靠，无需额外 shell 权限配置 |
| 4 | 测试脚本依赖 | pygetwindow+keyboard / 简化版 | pygetwindow+keyboard | 真实模拟操作记事本行为 |
| 5 | 项目结构 | monorepo | 单仓库，desktop/ + server/ + scripts/ 分离 | 方便管理，前后端独立开发部署 |
| 6 | 桌面端技术栈 | Tauri v2 + React + TypeScript + Vite | 按规划执行 | 符合项目规划文档要求 |

---

## 已完成部分

### 阶段 0 完成清单

- [x] Rust 工具链安装与配置 (rustc 1.96.0)
- [x] Tauri 桌面端项目初始化
  - Tauri v2 + React + TypeScript + Vite
  - `@tauri-apps/api` + `@tauri-apps/plugin-shell` 集成
  - Rust 自定义命令 `run_python_script` 用于调用 Python 脚本
  - 基础 UI 框架（健康检查 + 运行测试脚本）
- [x] FastAPI 后端项目初始化
  - FastAPI 0.115.6 + SQLAlchemy 2.0 + Alembic
  - 健康检查接口 `GET /health`
  - 应用启动时自动建表和初始化种子数据
- [x] 数据库模型（12 张表）
  - `users`, `email_codes`, `devices`, `plans`, `orders`
  - `memberships`, `trial_quotas`, `contacts`, `tasks`, `task_results`
  - `admin_users`, `admin_audit_logs`
- [x] Alembic 数据库迁移
  - 自动生成初始迁移脚本
  - 可正常执行 `alembic upgrade head`
- [x] 种子数据：三档套餐（月卡 ¥29.99 / 季卡 ¥69.99 / 年卡 ¥199.99）
- [x] Python 测试脚本 `scripts/test_autobot.py`
  - 打开记事本并输入 `123456`
  - 按标准 JSON 协议输出运行状态
- [x] 后端健康检查验证通过
- [x] Tauri Rust 代码编译通过

### 验证结果

```
# 健康检查
GET http://127.0.0.1:8000/health
→ {"status":"ok","app":"FriendAuto"}

# Tauri 编译
cargo check → 编译成功 (1 warning, 已修复)
```

---

## 项目结构

```
D:\FriendAuto/
├── desktop/                    # Tauri 桌面端工程
│   ├── src/                    # React + TypeScript 前端
│   │   ├── App.tsx             # 主界面组件
│   │   ├── App.css             # 主界面样式
│   │   ├── main.tsx            # 入口
│   │   └── index.css           # 全局样式
│   ├── src-tauri/              # Tauri Rust 后端
│   │   ├── src/
│   │   │   ├── lib.rs          # Tauri 应用入口 + 自定义命令
│   │   │   └── main.rs         # 启动入口
│   │   ├── Cargo.toml          # Rust 依赖
│   │   ├── tauri.conf.json     # Tauri 配置
│   │   └── capabilities/       # 权限配置
│   ├── package.json
│   └── vite.config.ts
├── server/                     # FastAPI 后端工程
│   ├── app/
│   │   ├── main.py             # FastAPI 应用入口
│   │   ├── seed.py             # 数据库初始化 + 种子数据
│   │   ├── core/
│   │   │   ├── config.py       # 配置（pydantic-settings）
│   │   │   ├── database.py     # SQLAlchemy 引擎 + Session
│   │   │   ├── security.py     # JWT + 密码哈希
│   │   │   └── deps.py         # 依赖注入
│   │   ├── api/
│   │   │   └── health.py       # 健康检查接口
│   │   ├── models/             # SQLAlchemy ORM 模型
│   │   │   ├── user.py
│   │   │   ├── email_code.py
│   │   │   ├── device.py
│   │   │   ├── plan.py
│   │   │   ├── order.py
│   │   │   ├── membership.py
│   │   │   ├── trial_quota.py
│   │   │   ├── contact.py
│   │   │   ├── task.py
│   │   │   ├── task_result.py
│   │   │   ├── admin_user.py
│   │   │   └── admin_audit_log.py
│   │   ├── schemas/           # Pydantic schema（待填充）
│   │   └── services/          # 业务逻辑层（待填充）
│   ├── alembic/                # 数据库迁移
│   │   ├── versions/
│   │   │   └── 56364eee2324_init.py
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── alembic.ini
│   ├── .env                    # 环境变量
│   ├── requirements.txt        # Python 依赖
│   └── friendauto.db           # SQLite 数据库文件
├── scripts/
│   └── test_autobot.py         # 测试自动化脚本
├── start_server.bat            # 后端启动脚本
├── start_desktop.bat           # 桌面端启动脚本
├── PROJECT_PLAN.md             # 项目规划文档
└── PROJECT_MANAGEMENT.md       # 项目管理文档（本文件）
```

---

## 重要文件修改记录

| 日期 | 文件 | 修改内容 | 备注 |
|------|------|----------|------|
| 2026-06-24 | `PROJECT_PLAN.md` | 新增项目规划文档 | 项目总纲 |
| 2026-06-24 | `desktop/package.json` | 添加 Tauri 依赖和 script | Tauri v2 + React + TS |
| 2026-06-24 | `desktop/src-tauri/tauri.conf.json` | 配置应用信息 | identifier, windows |
| 2026-06-24 | `desktop/src-tauri/Cargo.toml` | 添加 tauri-plugin-shell 依赖 | 用于进程管理 |
| 2026-06-24 | `desktop/src-tauri/src/lib.rs` | 添加 run_python_script 命令 | Rust 调用 Python 脚本 |
| 2026-06-24 | `desktop/src/App.tsx` | 替换为 FriendAuto 主界面 | 健康检查 + 脚本运行 |
| 2026-06-24 | `server/requirements.txt` | 新增后端 Python 依赖 | FastAPI 全家桶 |
| 2026-06-24 | `server/app/main.py` | FastAPI 应用入口 | 含 lifespan 自动建表 |
| 2026-06-24 | `server/app/models/*.py` | 12 个数据库模型 | 完整数据表定义 |
| 2026-06-24 | `server/alembic/versions/56364eee2324_init.py` | 初始数据库迁移 | 自动生成的迁移脚本 |
| 2026-06-24 | `scripts/test_autobot.py` | 测试自动化脚本 | 打开记事本输入 123456 |

---

## 待办事项

### 阶段 0 遗留（低优先级）
- [ ] 安装测试脚本依赖 `pip install pygetwindow keyboard`
- [ ] 桌面端编写完整的启动/运行逻辑（当前仅为原型验证界面）

### 阶段 1 — 高优先级
- [ ] 邮箱验证码发送接口 `POST /auth/send-code`
- [ ] 验证码登录/注册接口 `POST /auth/login`
- [ ] Token 刷新接口 `POST /auth/refresh`
- [ ] 机器码生成（桌面端 Rust 侧）
- [ ] 设备绑定接口 `POST /devices/bind`
- [ ] 设备状态查询 `GET /devices/current`
- [ ] 登录页面 UI
- [ ] Token 本地持久化存储

### 阶段 2 — 中优先级
- [ ] 会员状态接口 `GET /me/status`
- [ ] 套餐列表接口 `GET /plans`
- [ ] 试用次数扣减逻辑
- [ ] 充值弹窗 UI
- [ ] 微信支付对接
- [ ] 支付宝支付对接

### 阶段 3 — 中优先级
- [ ] 主任务界面（每日限额、标签、打招呼语）
- [ ] 开始/停止任务
- [ ] 实时日志展示
- [ ] 结果上报接口 `POST /tasks/{id}/results`
- [ ] 真实自动化脚本替换

### 阶段 4 — 中优先级
- [ ] 后台管理界面
- [ ] 用户/设备/会员管理
- [ ] 套餐价格配置
- [ ] 订单管理
- [ ] 任务日志查询

### 阶段 5 — 低优先级
- [ ] Windows `.exe` 打包
- [ ] 自动更新
- [ ] HTTPS 部署
- [ ] 接口限流
- [ ] 代码签名

---

## 架构思路

### 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Windows 桌面端 (Tauri)                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │             React + TypeScript UI                    │ │
│  │  (登录页 / 充值弹窗 / 任务面板 / 日志展示)            │ │
│  └──────────────┬──────────────────────────────────────┘ │
│                 │ invoke() / fetch()                     │
│  ┌──────────────▼──────────────────────────────────────┐ │
│  │              Tauri Rust 层                           │ │
│  │  - run_python_script 命令                            │ │
│  │  - 机器码生成（待实现）                                │ │
│  │  - Token 持久化存储（待实现）                          │ │
│  └──────────────┬──────────────────────────────────────┘ │
└─────────────────┼────────────────────────────────────────┘
                  │ HTTPS API
┌─────────────────▼────────────────────────────────────────┐
│                 FastAPI 后端服务                          │
│  ┌──────────────┬──────────────┬──────────────────────┐  │
│  │ 账号/设备 API │ 会员/支付 API │ 任务/联系人 API      │  │
│  └──────────────┴──────────────┴──────────────────────┘  │
│                         │                                 │
│              ┌──────────▼──────────┐                      │
│              │   SQLite (dev)      │                      │
│              │   PostgreSQL (prod) │                      │
│              └─────────────────────┘                      │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│               Python 自动化程序 (外部进程)                  │
│  接收 JSON 参数 → 执行微信自动化 → 返回 JSON 结果         │
│  通信方式：stdin/stdout (子进程)                           │
└──────────────────────────────────────────────────────────┘
```

### 关键架构原则

1. **服务端是唯一可信来源**：会员状态、试用次数、设备绑定均由服务端裁决
2. **进程隔离**：桌面端与自动化程序通过 JSON over stdin/stdout 通信
3. **幂等处理**：关键接口（扣次、支付回调）必须幂等
4. **不可篡改**：客户端不保存真实会员判断结果，不保存支付密钥
5. **可切换数据库**：SQLAlchemy ORM 屏蔽数据库差异，开发 SQLite → 部署 PostgreSQL

### 通信协议

桌面端 → 自动化程序：
```json
{"run_id": "...", "daily_limit": 20, "contacts": [...]}
```

自动化程序 → 桌面端（逐行 JSON）：
```json
{"run_id": "...", "contact_id": "...", "event": "success|failed|invalid", "message": "...", "timestamp": "..."}
```

仅 `event = success` 扣试用次数。

---

## Git 提交历史

```
87400c5 feat: add project management document
e6e46ca feat: integrate test script with tauri desktop
88094fb feat: add test automation script and seed data
c4cfc19 feat: init fastapi backend with models and migrations
cf93f1b feat: init tauri desktop project with shell plugin
6068ccd Initial commit
```

---

*本文档随着项目推进持续更新。每个阶段完成后更新一次。*
