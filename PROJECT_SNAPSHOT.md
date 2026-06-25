# FriendAuto — 项目状态快照

更新时间：2026-06-25
项目目录：`D:\FriendAuto`
远程仓库：`https://github.com/zzw-0912/AddFriendAuto.git`
分支：`master`

---

## 一、项目目标

FriendAuto 是一款 Windows 桌面应用，客户通过 `.exe` 安装后，完成**邮箱密码注册/登录** → **设备绑定** → **会员充值或试用** → **配置每日自动加好友任务**。桌面端负责传参给已有 Python 自动化程序、启动程序、接收结果、上报服务器。

---

## 二、架构思路

### 总体架构

```
Windows 桌面端 (Tauri v2 + React + TypeScript)
    │
    │ HTTPS REST API (http://127.0.0.1:8001)
    ▼
FastAPI 后端服务 (SQLAlchemy ORM)
    │
    ▼
SQLite (开发) / PostgreSQL (生产)

Windows 桌面端
    │
    │ 本地进程 (std::process::Command → stdin/stdout JSON)
    ▼
Python 自动化程序 (scripts/test_autobot.py → 替换为真实脚本)
```

### 职责划分

| 层 | 职责 | 不负责 |
|---|---|---|
| **桌面端** | UI、登录(邮箱+密码)、机器码采集、展示状态、启动脚本、展示日志、上报结果 | 不判断会员/密码/试用 |
| **后端** | 注册登录、密码哈希(bcrypt)、验证码校验、token 签发、设备绑定、会员判断、试用扣次、订单创建、支付回调、任务校验、结果记录 | — |
| **Python 脚本** | 接收参数、执行自动化、返回结果 | 不判断会员、充值、试用 |
| **后台管理** | 用户管理、设备改绑、会员操作、订单查看、任务日志、操作审计 | — |

### 安全设计

- 密码用 bcrypt 哈希存储
- 商业规则由服务端裁决，客户端只展示服务端返回的状态
- 支付密钥只存在于服务端
- 试用次数保存在服务端，卸载重装不能重置
- 机器码上传前做 SHA256 哈希，不上传明文硬件信息
- 关键接口（扣次、支付回调）做幂等处理
- 支付成功以服务端回调验签为准，不信任客户端轮询

---

## 三、关键决策

### 产品决策

| 决策 | 说明 |
|------|------|
| 邮箱密码登录 | 注册时设密码，日常用邮箱+密码登录；注册和找回密码需验证码 |
| 一个账号一台设备 | 默认绑定一台设备，第二台拦截，需要管理员后台改绑 |
| 20 次试用额度 | 新用户自动获得 20 次成功加好友额度 |
| 按成功扣次 | 只有 `event = success` 才扣试用，失败/无效/异常不扣 |
| 会员覆盖试用 | 会员有效期内不扣试用次数 |
| 会员叠加 | 续费时新的有效期从当前有效期结束后开始 |
| 三档套餐 | 月卡 ¥29.9、季卡 ¥79.9、年卡 ¥299.9（价格由服务端配置） |
| 邮箱 SMTP 发送 | 使用 QQ邮箱 SMTP + 授权码，aiosmtplib 异步发送 HTML 模板邮件 |

### 技术决策

| 决策 | 说明 |
|------|------|
| Tauri v2 + React + TypeScript | 桌面端技术栈，原生窗口 + Web UI |
| FastAPI + SQLAlchemy | 后端框架 + ORM |
| SQLite 开发 / PostgreSQL 生产 | 环境切换通过 `database_url` 配置 |
| 密码哈希 (bcrypt) | 使用 `bcrypt` 库，与验证码的 SHA256 分开 |
| 验证码哈希 (SHA256) | passlib 和 bcrypt 5.x 不兼容，验证码短时效无需 bcrypt |
| 邮箱发送 (aiosmtplib) | 异步非阻塞发送，debug 模式返回 `dev_code` 方便联调 |
| 发送频率限制 | 同一邮箱 60 秒内只能发一次验证码 |
| WMIC csproduct UUID | Windows 机器码采集，不引入额外 Rust crate |
| 本地 JSON Token 存储 | `dirs_next::data_dir` + `auth.json`，在 `%APPDATA%/FriendAuto/auth.json` |
| `std::process::Command` | Rust 原生进程启动，不用 Tauri shell 插件 |
| 测试账号 | `test@friendauto.com` + `888888` 跳过密码+设备绑定检查 |
| 支付回调 mock | 开发环境直接 `POST /payments/*/callback?order_no=...` |
| Tauri 事件流通信 | Rust BufReader 逐行读 stdout → `emit("script-event")` → 前端 `listen()` |
| 子进程管理 | Tauri State `Mutex<Option<Child>>`，支持 start/stop 和进程清理 |

---

## 四、已完成部分

### 阶段 0：项目初始化与技术底座 ✅

- Tauri v2 + React + TypeScript + Vite 工程搭建
- FastAPI 后端工程，SQLAlchemy ORM，SQLite 数据库
- 13 张数据表自动创建
- 三档套餐数据种子
- 测试 Python 脚本 `scripts/test_autobot.py`
- 健康检查接口 `GET /health`
- 一键启动脚本 `start_server.bat`、`start_desktop.bat`

### 阶段 1：账号、登录与设备绑定 ✅

- `POST /auth/send-code` — 邮件验证码发送（QQ邮箱 SMTP 真实发送，debug 模式回显验证码）
- `POST /auth/login` — 邮箱+密码登录（自动设备绑定）
- `POST /auth/register` — 邮箱+密码+验证码注册（自动设备绑定+创建试用额度）
- `POST /auth/reset-password` — 验证码+新密码重置
- `POST /auth/refresh` — Token 刷新
- `POST /devices/bind` / `GET /devices/current` — 设备绑定与查询
- 验证码 SHA256 哈希存储 + 密码 bcrypt 哈希存储
- 机器码 WMIC + Token 持久化
- 桌面端三标签登录页（登录/注册/找回密码）—— 全新 UI 设计

### 阶段 2：会员、试用与充值 ✅

- `GET /me/status` — 会员 + 试用状态查询
- `GET /plans` — 套餐列表
- `POST /orders` — 创建订单 + `GET /orders/{id}` — 查询订单
- `POST /payments/wechat/callback` — 模拟微信支付回调
- `POST /payments/alipay/callback` — 模拟支付宝支付回调
- 新用户自动创建 20 次试用额度 + 会员叠加逻辑
- 桌面端充值弹窗（三栏套餐卡片 + 支付方式选择）
- 登录 UI 全新设计（设计系统复刻）

### 阶段 3：主界面与自动化脚本联调 ✅

- `POST /tasks/start-check` — 任务前校验
- `GET /contacts/search` — 联系人筛选
- `POST /tasks/{id}/results` — 结果上报（幂等扣次）
- `POST /tasks/{id}/finish` — 结束任务
- 桌面端任务面板 `TaskPanel.tsx`（配置/日志/计数器）
- Rust 脚本集成：stdin JSON + BufReader + Tauri 事件流
- 充值弹窗 `PaymentModal.tsx` 全面重设计

### 阶段 4：后台管理 ✅

- `POST /admin/login` — 管理员登录（独立 JWT）
- 用户管理：列表、详情、会员延长/冻结/解冻
- 设备管理：列表、解绑、改绑、备注编辑
- 套餐管理：价格在线配置
- 订单管理：列表、状态筛选
- 任务日志：列表、执行结果弹窗
- 操作审计：完整操作日志
- 独立 React 管理前端（7 个页面）

### 本次新增功能（2026-06-25 未提交）

| 功能 | 改动文件 |
|------|----------|
| **密码登录系统** | `auth_service.py` `auth.py` `schemas/auth.py` |
| **bcrypt 密码哈希** | `security.py` |
| **QQ邮箱真实邮件发送** | `email_service.py`（新建）`auth_service.py` |
| **发送频率限制** | `auth_service.py`（60秒防滥用） |
| **数据库迁移** | `seed.py`（给旧表加 password_hash 列） |
| **登录 UI 全新设计** | `LoginPage.tsx` `App.css`（720px 高度，color-mix 取色） |
| **SMTP 配置** | `config.py` `.env` |

---

## 五、API 接口清单

### 认证相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/send-code` | 发送邮箱验证码（含 60 秒频率限制） |
| POST | `/auth/login` | 邮箱+密码登录（自动设备绑定） |
| POST | `/auth/register` | 邮箱+密码+验证码注册 |
| POST | `/auth/reset-password` | 验证码+新密码重置 |
| POST | `/auth/refresh` | 刷新 token |

### 设备相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/devices/bind` | 绑定设备 |
| GET | `/devices/current` | 当前设备信息 |

### 会员与支付

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/me/status` | 会员+试用状态 |
| GET | `/plans` | 套餐列表 |
| POST | `/orders` | 创建订单 |
| GET | `/orders/{id}` | 订单详情 |
| POST | `/payments/wechat/callback` | 微信支付回调（mock） |
| POST | `/payments/alipay/callback` | 支付宝支付回调（mock） |

### 任务与联系人

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks/start-check` | 任务前校验 |
| GET | `/contacts/search` | 搜索联系人 |
| POST | `/tasks/{id}/results` | 上报执行结果 |
| POST | `/tasks/{id}/finish` | 结束任务 |

### 后台管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/login` | 管理员登录 |
| GET | `/admin/users` | 用户列表 |
| GET | `/admin/users/{id}` | 用户详情 |
| PATCH | `/admin/users/{id}/membership` | 修改会员 |
| GET | `/admin/devices` | 设备列表 |
| PATCH | `/admin/devices/{id}` | 更新设备 |
| POST | `/admin/devices/{id}/rebind` | 设备改绑 |
| GET | `/admin/plans` | 套餐列表 |
| PATCH | `/admin/plans/{id}` | 更新套餐 |
| GET | `/admin/orders` | 订单列表 |
| GET | `/admin/tasks` | 任务日志 |
| GET | `/admin/tasks/{id}/results` | 任务明细 |
| GET | `/admin/audit-logs` | 操作审计 |
| GET | `/admin/contacts` | 联系人搜索 |

---

## 六、数据库设计（13 张表）

| 表名 | 核心字段 | 用途 |
|------|---------|------|
| `users` | id, email, **password_hash**, status, created_at, last_login_at | 用户账号（含密码） |
| `email_codes` | id, email, code_hash, expires_at, used_at, created_at | 验证码 |
| `devices` | id, user_id, machine_code_hash, status, bound_at, last_seen_at | 设备绑定 |
| `plans` | id, name, duration_days, price_cents, enabled | 套餐配置 |
| `orders` | id, order_no, user_id, plan_id, amount_cents, payment_channel, status | 订单 |
| `memberships` | id, user_id, starts_at, ends_at, status | 会员期限 |
| `trial_quotas` | id, user_id, device_id, total_count, used_count, remaining_count | 试用额度 |
| `tasks` | id, user_id, device_id, daily_limit, create_tag, greeting_text, status | 任务记录 |
| `task_results` | id, task_id, contact_id, result, message, trial_charged | 任务执行结果 |
| `contacts` | id, wechat_nickname, wechat_id, tag, status | 联系人数据 |
| `payments` | id, order_id, channel, transaction_id, amount_cents, status | 支付记录 |
| `admin_users` | id, username, password_hash, role, status | 后台管理员 |
| `admin_audit_logs` | id, admin_user_id, action, target_type, target_id, detail | 操作审计 |

---

## 七、待办事项

### 阶段 5 — 上线前必须完成

- [ ] 真实微信支付接入（验签、回调）
- [ ] 真实支付宝支付接入（验签、回调）
- [ ] 支付幂等处理（防止重复回调）
- [ ] PostgreSQL 生产环境切换
- [ ] Windows `.exe` 打包（Tauri build）
- [ ] 客户端自动更新（Tauri updater）
- [ ] HTTPS 服务部署（Nginx + SSL）
- [ ] 接口限流（验证码、订单、任务）
- [ ] 客户端日志导出
- [ ] 网络断开时的错误提示和状态处理
- [ ] 代码签名（减少 Windows 安全提示）
- [ ] 用户协议、隐私政策
- [ ] 异常告警和服务器监控
- [ ] 安装包在干净 Windows 环境验证

---

## 八、项目结构

```
D:\FriendAuto/
├── desktop/                    # Tauri 桌面端
│   ├── src/                    # React + TypeScript
│   │   ├── App.tsx             # 应用入口
│   │   ├── App.css             # 设计系统（color-mix 取色）
│   │   ├── LoginPage.tsx       # 三标签登录页（密码+验证码）
│   │   ├── MainPage.tsx        # 主页面
│   │   ├── MainPage.css        # 主页面样式
│   │   ├── TaskPanel.tsx       # 任务面板
│   │   └── PaymentModal.tsx    # 充值弹窗
│   └── src-tauri/              # Rust 后端
│       └── src/
│           ├── lib.rs          # 机器码/Token/start_task/stop_task
│           └── main.rs
├── server/                     # FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 应用入口
│   │   ├── seed.py             # 建表+种子数据+数据库迁移
│   │   ├── core/
│   │   │   ├── config.py       # pydantic-settings（含 SMTP 配置）
│   │   │   ├── database.py     # SQLAlchemy 引擎
│   │   │   ├── security.py     # JWT + SHA256 + bcrypt
│   │   │   └── deps.py         # 依赖注入
│   │   ├── api/                # 路由（auth/devices/status/plans/orders/payments/tasks/contacts/admin）
│   │   ├── models/             # ORM 模型（13 张表）
│   │   ├── schemas/            # Pydantic schema
│   │   └── services/           # 业务逻辑（含 email_service.py 邮件发送）
│   ├── alembic/
│   ├── .env                    # SMTP 配置（gitignored）
│   └── friendauto.db           # SQLite 数据库
├── scripts/
│   └── test_autobot.py         # 测试自动化脚本
├── admin/                      # 管理后台前端（Vite + React）
├── start_server.bat
├── start_desktop.bat
├── PROJECT_PLAN.md             # 项目规划
├── PROJECT_MANAGEMENT.md       # 项目管理
└── PROJECT_SNAPSHOT.md         # 本文件
```

---

## 九、脚本通信协议

### 桌面端 → 脚本（stdin JSON）

```json
{
  "run_id": "task_001",
  "daily_limit": 20,
  "create_tag": true,
  "greeting_text": "你好，我是XXX",
  "contacts": [
    { "contact_id": 1001, "wechat_nickname": "张三", "wechat_id": "wxid_zhangsan" }
  ]
}
```

### 脚本 → 桌面端（stdout 逐行 JSON）

```json
{ "run_id": "task_001", "event": "started", "message": "开始任务，共 3 个联系人", "timestamp": "..." }
{ "run_id": "task_001", "contact_id": 1001, "event": "success", "message": "张三 添加成功", "timestamp": "..." }
{ "run_id": "task_001", "event": "finished", "message": "任务完成", "timestamp": "..." }
```

### 事件类型

| 事件 | 说明 | 扣次 |
|------|------|:----:|
| `started` | 脚本启动 | 否 |
| `progress` | 处理中 | 否 |
| `success` | 添加成功 | 是（无会员时） |
| `failed` | 添加失败 | 否 |
| `invalid` | 无效联系人 | 否 |
| `finished` | 任务完成 | 否 |
| `error` | 脚本异常 | 否 |
| `exited` | 进程退出（Rust 发送） | 否 |

扣次规则：仅 `event = success` 且无活跃会员时才扣试用次数，`run_id + contact_id` 组合幂等。

---

## 十、开发环境

### 启动命令

```bash
# 后端
cd server
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 桌面端
cd desktop
npm run tauri dev

# 管理后台
cd admin
npm run dev
```

### 测试账号

- 邮箱：`test@friendauto.com`
- 密码/验证码：`888888`
- 特点：debug 模式下跳过密码验证和设备绑定

### 常用操作

- 重置数据库：删除 `server/friendauto.db`，重启后端自动重建
- Python 脚本测试：`echo '{"run_id":"test","contacts":[]}' | python scripts/test_autobot.py`
