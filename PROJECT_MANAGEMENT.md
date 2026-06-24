# FriendAuto 项目管理文档

> 用于阶段交接，记录当前阶段关键决策、已完成部分、待办事项、重要文件修改记录和架构思路。

---

## 当前阶段：阶段 1 — 账号、登录与设备绑定

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
| 7 | 验证码哈希算法 | passlib+bcrypt / hashlib.sha256 | hashlib.sha256 | passlib 与 bcrypt 5.x 不兼容，验证码短时效无需 bcrypt |
| 8 | 登录设备绑定时机 | 登录时自动绑 / 手动绑定 | 登录时自动绑定 + 手动绑定 API | 简化用户体验，首次登录即完成绑定 |
| 9 | 机器码生成方式 | machine-uid crate / WMIC / sysinfo | WMIC csproduct UUID | 无需额外 Rust 依赖，Windows 原生支持 |
| 10 | Token 持久化 | Tauri store plugin / 本地 JSON 文件 | 本地 JSON 文件 (`dirs_next::data_dir`) | 最简单可靠，不依赖额外插件 |

---

## 已完成部分

### 阶段 0 完成清单

- [x] Rust 工具链安装与配置 (rustc 1.96.0)
- [x] Tauri 桌面端项目初始化
- [x] FastAPI 后端项目初始化
- [x] 数据库模型（12 张表）
- [x] Alembic 数据库迁移
- [x] 种子数据：三档套餐（月卡 ¥29.99 / 季卡 ¥69.99 / 年卡 ¥199.99）
- [x] Python 测试脚本
- [x] 后端健康检查 + Tauri 编译通过

### 阶段 1 完成清单

- [x] `POST /auth/send-code` — 邮箱验证码发送接口
  - 开发模式下返回 `dev_code` 方便联调
- [x] `POST /auth/login` — 验证码登录/注册
  - 新邮箱自动注册
  - 登录时自动绑定当前设备（首次）
  - 第二台设备登录返回 403
  - 机器已被其他账号绑定时返回 403
- [x] `POST /auth/refresh` — Token 刷新
- [x] `POST /devices/bind` — 设备手动绑定
- [x] `GET /devices/current` — 当前设备状态查询
- [x] 桌面端 `get_machine_code` — 机器码生成（WMIC csproduct UUID）
- [x] 桌面端 `save_token` / `load_token` / `clear_token` — Token 持久化
- [x] 桌面端登录页面 `LoginPage.tsx`
  - 邮箱输入 → 发送验证码 → 输入验证码 → 登录
  - 登录成功后自动跳转主界面
- [x] 桌面端主页面 `MainPage.tsx`
  - 显示当前用户邮箱
  - 退出登录按钮
  - 健康检查 + 脚本运行（保留阶段 0 功能）

### 验证结果

```
# 后端集成测试全部通过
POST /auth/send-code     → {"message":"Code sent"}
POST /auth/login         → {"access_token":"...", "is_new_user": true}
GET  /devices/current    → {"id":1, "user_id":1, "status":"active"}
POST /auth/refresh       → {"access_token":"..."}
第二设备登录测试         → 403 Account already bound to another device
他人占用机器登录测试     → 403 Device already bound to another account

# Tauri 编译
cargo check → 编译成功 (0 warnings)

# 桌面端
- 机器码生成: WMIC csproduct UUID
- Token 持久化: %APPDATA%/FriendAuto/auth.json
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
| 2026-06-24 | `server/app/api/auth.py` | 新增认证 API 路由 | send-code, login, refresh |
| 2026-06-24 | `server/app/api/devices.py` | 新增设备 API 路由 | bind, current |
| 2026-06-24 | `server/app/schemas/auth.py` | 认证请求/响应 Schema | Pydantic 模型 |
| 2026-06-24 | `server/app/schemas/device.py` | 设备请求/响应 Schema | Pydantic 模型 |
| 2026-06-24 | `server/app/services/auth_service.py` | 认证业务逻辑 | 含设备绑定逻辑 |
| 2026-06-24 | `server/app/services/device_service.py` | 设备业务逻辑 | 绑定/查询 |
| 2026-06-24 | `server/app/core/security.py` | 替换为 SHA256 | 修复 passlib/bcrypt 兼容问题 |
| 2026-06-24 | `server/app/core/config.py` | 添加 refresh_token 配置 | |
| 2026-06-24 | `server/app/main.py` | 注册 auth 和 devices 路由 | |
| 2026-06-24 | `desktop/src-tauri/src/lib.rs` | 添加机器码 + token 存储命令 | 4 个新 Tauri 命令 |
| 2026-06-24 | `desktop/src-tauri/Cargo.toml` | 添加 dirs-next 依赖 | |
| 2026-06-24 | `desktop/src/App.tsx` | 重构为登录/主界面路由 | 自动恢复 token |
| 2026-06-24 | `desktop/src/LoginPage.tsx` | 登录页面组件 | 新增 |
| 2026-06-24 | `desktop/src/MainPage.tsx` | 主页面组件 | 从 App.tsx 拆分 |
| 2026-06-24 | `desktop/src/App.css` | 添加登录页样式 | 输入框、按钮、错误提示 |

---

## 待办事项

### 阶段 0 遗留（低优先级）
- [ ] 安装测试脚本依赖 `pip install pygetwindow keyboard`
- [ ] 桌面端编写完整的启动/运行逻辑（当前仅为原型验证界面）

### 阶段 2 — 高优先级
- [ ] `GET /me/status` — 会员、试用、设备、版本综合状态接口
- [ ] `GET /plans` — 套餐列表接口
- [ ] 试用次数初始化（新注册用户自动获得 20 次）
- [ ] 试用次数扣减逻辑（仅 `success` 事件扣次，幂等）
- [ ] `POST /orders` — 创建充值订单
- [ ] `POST /payments/wechat/callback` — 微信支付回调
- [ ] `POST /payments/alipay/callback` — 支付宝支付回调
- [ ] 桌面端充值弹窗 UI
- [ ] 会员过期重新校验流程
- [ ] 桌面端会员/试用状态展示

### 阶段 3 — 中优先级
- [ ] `POST /tasks/start-check` — 任务前校验接口
- [ ] `GET /contacts/search` — 联系人筛选接口
- [ ] `POST /tasks/{id}/results` — 结果上报接口（幂等）
- [ ] 主任务界面（每日限额、标签、打招呼语）
- [ ] 开始/停止任务
- [ ] 实时日志展示
- [ ] 真实自动化脚本替换

### 阶段 4 — 中优先级
- [ ] 后台管理界面（React 或独立页面）
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
0079f9d feat: add login page and main page UI
4ab259c feat: add machine code generation and token storage
ce638e9 feat: add auth and device APIs
7e7a0da docs: add project management document for stage 0
d207f97 feat: add test automation script
3b1cb68 feat: init fastapi backend with models and migrations
3cd467a feat: add main desktop UI with health check and script runner
94ff687 feat: init tauri desktop project
6068ccd Initial commit
```

*本文档随着项目推进持续更新。每个阶段完成后更新一次。*
