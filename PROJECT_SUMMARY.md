# FriendAuto 项目总结

> 生成时间：2026-06-25
> 远程仓库：`https://github.com/zzw-0912/AddFriendAuto.git`

---

## 一、项目关键决策

### 产品决策

| 决策 | 说明 |
|------|------|
| 邮箱验证码登录 | 无密码模式，6 位验证码，无需记住密码 |
| 一个账号一台设备 | 默认绑定一台设备，第二台拦截，需管理员后台改绑 |
| 20 次试用额度 | 新用户自动获得 20 次成功加好友额度 |
| 按成功扣次 | 只有 `event = success` 才扣试用，失败/无效/异常不扣 |
| 会员覆盖试用 | 会员有效期内不扣试用次数 |
| 会员叠加 | 续费时新有效期从当前有效期结束后开始 |
| 三档套餐 | 月卡 ¥29.9、季卡 ¥69.9、年卡 ¥199.9（价格由服务端配置） |
| 软件定位 | 只处理客户自有或已授权的微信联系人名单 |

### 技术决策

| 决策 | 说明 |
|------|------|
| Tauri v2 + React + TypeScript | 桌面端技术栈，原生窗口 + Web UI |
| FastAPI + SQLAlchemy | 后端框架 + ORM |
| SQLite 开发 / PostgreSQL 生产 | 环境切换通过 `database_url` 配置 |
| SHA256 验证码哈希 | passlib 与 bcrypt 5.x 不兼容，改用 hashlib |
| WMIC csproduct UUID | Windows 机器码采集，不引入额外 Rust crate |
| 本地 JSON Token 存储 | `%APPDATA%/FriendAuto/auth.json` |
| `std::process::Command` | Rust 原生进程启动，不用 Tauri shell 插件 |
| 测试账号免绑定 | `test@friendauto.com` + `888888` 跳过设备绑定检查 |
| 支付回调 mock | 开发环境直接 `POST /payments/*/callback?order_no=...` |
| Tauri 事件流通信 | Rust BufReader → `emit("script-event")` → 前端 `listen()` |
| 子进程管理 | Tauri State `Mutex<Option<Child>>`，支持 start/stop |
| 管理员独立 JWT | sub 前缀 `admin_` 区分用户 token，不可互用 |

### 安全决策

- 服务端是唯一可信来源：会员状态、试用次数、设备绑定均由服务端裁决
- 支付密钥只存在于服务端
- 试用次数保存在服务端，卸载重装不能重置
- 机器码上传前做 SHA256 哈希
- 关键接口（扣次、支付回调）做幂等处理
- 支付成功以服务端回调验签为准
- 管理员 token 与用户 token 隔离

---

## 二、已完成部分

### 阶段 0：项目初始化与技术底座 ✅

**7 次提交**，涵盖：
- Tauri v2 + React + TypeScript + Vite 桌面工程搭建
- FastAPI 后端 + SQLAlchemy ORM + 12 张数据表（自动创建）
- SQLite 开发数据库 + Alembic 迁移
- 三档套餐种子数据（月卡 ¥29.9/30天、季卡 ¥69.9/90天、年卡 ¥199.9/365天）
- 测试 Python 脚本 `scripts/test_autobot.py`
- 健康检查接口 + 一键启动脚本

### 阶段 1：账号、登录与设备绑定 ✅

**5 次提交**，涵盖：
- `POST /auth/send-code` — 发送验证码（开发模式回显验证码）
- `POST /auth/login` — 验证码登录/注册（自动注册 + 自动设备绑定）
- `POST /auth/refresh` — Token 刷新
- `POST /devices/bind` / `GET /devices/current` — 设备绑定/查询
- 桌面端机器码生成（WMIC csproduct UUID）+ Token 持久化
- 三标签登录页（登录 / 注册 / 找回）
- 测试账号 `test@friendauto.com` / `888888` 跳过设备绑定

### 阶段 2：会员、试用与充值 ✅

**3 次提交**，涵盖：
- `GET /me/status` — 会员 + 试用状态查询
- `GET /plans` / `POST /orders` / `GET /orders/{id}` — 套餐+订单
- `POST /payments/*/callback` — 模拟微信/支付宝支付回调
- 新用户自动创建 20 次试用额度 + 会员叠加逻辑
- 桌面端充值弹窗（三栏套餐卡片 + 支付方式选择 + 跳过试用）
- 登录 UI 全面重设计（品牌面板、倒计时、表单验证）

### 阶段 3：主界面与自动化脚本联调 ✅

**4 次提交（95d08e0）**，涵盖：
- `POST /tasks/start-check` — 任务前校验（会员/试用/设备状态）
- `GET /contacts/search` — 联系人模糊搜索
- `POST /tasks/{id}/results` — 结果上报（幂等扣次）
- `POST /tasks/{id}/finish` — 结束任务
- 桌面端任务面板 `TaskPanel.tsx` — 限额、标签、打招呼语、开始/停止
- 实时日志滚动展示（颜色区分 success/failed/invalid/error）
- 计数器 + 状态展示（会员到期/试用剩余）
- Rust 脚本集成：stdin JSON + BufReader + Tauri 事件流
- 脚本重写：stdin 读 JSON → 模拟 3 个联系人 → 逐行 JSON stdout

### 阶段 4：后台管理 ✅

**未提交（工作区）**，涵盖：
- 14 个 Admin API 端点（管理员登录/用户/设备/套餐/订单/任务/审计）
- 管理员独立 JWT 认证（`get_current_admin` 依赖注入）
- 默认管理员 `admin` / `admin123`
- 操作审计日志自动记录
- 独立 React 管理前端（7 个页面：概览/用户管理/设备管理/套餐管理/订单管理/任务日志/操作审计）

---

## 三、待办事项

### 阶段 5 — 上线前必须完成

| 优先级 | 任务 | 依赖 |
|--------|------|------|
| 🔴 高 | 真实微信支付接入（验签、回调） | 微信商户号 |
| 🔴 高 | 真实支付宝支付接入（验签、回调） | 支付宝应用 |
| 🔴 高 | 支付幂等处理（防止重复回调） | 支付接入后 |
| 🔴 高 | PostgreSQL 生产环境切换 | 数据库准备 |
| 🟡 中 | Windows `.exe` 打包 | Tauri build |
| 🟡 中 | 客户端自动更新 | Tauri updater |
| 🟡 中 | HTTPS 服务部署 | 域名 + 证书 |
| 🟡 中 | 接口限流（验证码/订单/任务） | 后端中间件 |
| 🟡 中 | 客户端日志导出 | 调试/售后 |
| 🟡 中 | 网络断开错误提示和状态处理 | 前端异常处理 |
| 🟢 低 | 代码签名 | 签名证书 |
| 🟢 低 | 用户协议 + 隐私政策 + 数据删除机制 | 法务确认 |
| 🟢 低 | 异常告警和服务器监控 | 部署后 |
| 🟢 低 | 安装包在干净 Windows 环境验证 | 打包后 |

### 后备任务

- 真实邮箱 SMTP 接入（替换 print 发送验证码）
- 联系人后台批量导入
- 多语言支持

---

## 四、项目结构

```
D:\FriendAuto/
├── desktop/                     # Tauri 桌面端工程
│   ├── src/                     # React + TypeScript 前端
│   │   ├── App.tsx              # 应用入口（路由）
│   │   ├── LoginPage.tsx        # 登录/注册/找回
│   │   ├── MainPage.tsx         # 主界面（状态栏 + 任务面板 + 充值）
│   │   ├── TaskPanel.tsx        # 任务面板（配置/日志/计数器）
│   │   ├── PaymentModal.tsx     # 充值弹窗（三栏卡片）
│   │   └── *.css                # 样式
│   └── src-tauri/               # Tauri Rust 后端
│       └── src/lib.rs           # 命令：机器码/Token/start_task/stop_task
├── server/                      # FastAPI 后端工程
│   ├── app/
│   │   ├── main.py              # 应用入口
│   │   ├── seed.py              # 数据库初始化和种子数据
│   │   ├── core/                # 配置/数据库/Security/依赖注入
│   │   ├── models/              # 12 张 ORM 模型
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── services/            # 业务逻辑层
│   │   └── api/                 # API 路由层
│   ├── alembic/                 # 数据库迁移
│   └── friendauto.db            # SQLite 数据库
├── admin/                       # 独立管理后台前端（未提交）
│   └── src/                     # 7 个管理页面
├── scripts/
│   └── test_autobot.py          # 测试自动化脚本
├── start_server.bat             # 后端启动
├── start_desktop.bat            # 桌面端启动
└── start_admin.bat              # 管理后台启动（未提交）
```

---

## 五、架构思路

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

管理后台 (React 独立前端)
    │
    │ HTTPS REST API (独立 JWT 认证)
    ▼
FastAPI 后端服务
```

### 桌面端 ↔ 脚本通信

```
[前端] invoke("start_task", {configJson})
  → [Rust] spawn python → stdin.write(config)
  → [Python] 读取 stdin → 处理联系人 → stdout JSON 逐行
  → [Rust] BufReader 逐行读取 → emit("script-event", line)
  → [前端] listen("script-event") → 解析 → 更新日志/计数器
  → 每条 success 事件 → POST /tasks/{id}/results
  → [用户点击停止] → invoke("stop_task") → kill 子进程
```

### 职责划分

| 层 | 负责 | 不负责 |
|---|---|---|
| 桌面端 | UI、登录、机器码、启动脚本、展示日志、上报结果 | 判断会员/试用、保存支付密钥 |
| 后端 | 登录、验证码、Token、设备绑定、会员、扣次、订单、支付、任务 | — |
| Python 脚本 | 接收参数、执行自动化、返回结果 | 判断会员/充值/试用 |
| 管理后台 | 用户/设备/会员/套餐/订单/任务/审计管理 | — |

---

## 六、API 接口清单

| 方法 | 路径 | 说明 | 阶段 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 0 ✓ |
| POST | `/auth/send-code` | 发送邮箱验证码 | 1 ✓ |
| POST | `/auth/login` | 登录/注册（含设备绑定、试用创建） | 1 ✓ |
| POST | `/auth/refresh` | 刷新 token | 1 ✓ |
| POST | `/devices/bind` | 绑定设备 | 1 ✓ |
| GET | `/devices/current` | 当前设备信息 | 1 ✓ |
| GET | `/me/status` | 会员 + 试用状态 | 2 ✓ |
| GET | `/plans` | 套餐列表 | 2 ✓ |
| POST | `/orders` | 创建订单 | 2 ✓ |
| GET | `/orders/{id}` | 订单详情 | 2 ✓ |
| POST | `/payments/wechat/callback` | 微信支付回调（mock） | 2 ✓ |
| POST | `/payments/alipay/callback` | 支付宝支付回调（mock） | 2 ✓ |
| POST | `/tasks/start-check` | 任务前校验 | 3 ✓ |
| GET | `/contacts/search` | 搜索联系人 | 3 ✓ |
| POST | `/tasks/{id}/results` | 上报结果（幂等扣次） | 3 ✓ |
| POST | `/tasks/{id}/finish` | 结束任务 | 3 ✓ |
| POST | `/admin/login` | 管理员登录 | 4 ✓ |
| GET | `/admin/users` | 用户列表 | 4 ✓ |
| GET | `/admin/users/{id}` | 用户详情 | 4 ✓ |
| PATCH | `/admin/users/{id}/membership` | 延长/冻结/解冻会员 | 4 ✓ |
| GET | `/admin/devices` | 设备列表 | 4 ✓ |
| PATCH | `/admin/devices/{id}` | 解绑/编辑 | 4 ✓ |
| POST | `/admin/devices/{id}/rebind` | 设备改绑 | 4 ✓ |
| GET | `/admin/plans` | 套餐列表 | 4 ✓ |
| PATCH | `/admin/plans/{id}` | 更新套餐 | 4 ✓ |
| GET | `/admin/orders` | 订单列表 | 4 ✓ |
| GET | `/admin/tasks` | 任务日志 | 4 ✓ |
| GET | `/admin/tasks/{id}/results` | 任务执行明细 | 4 ✓ |
| GET | `/admin/audit-logs` | 操作审计 | 4 ✓ |
| GET | `/admin/contacts` | 联系人搜索 | 4 ✓ |

---

## 七、数据库设计（12 张表）

| 表名 | 核心字段 | 用途 |
|------|---------|------|
| `users` | id, email, status, created_at, last_login_at | 用户账号 |
| `email_codes` | id, email, code_hash, expires_at, used_at | 验证码 |
| `devices` | id, user_id, machine_code_hash, status, bound_at, remark | 设备绑定 |
| `plans` | id, name, duration_days, price_cents, enabled | 套餐配置 |
| `orders` | id, order_no, user_id, plan_id, amount_cents, payment_channel, status | 订单 |
| `memberships` | id, user_id, starts_at, ends_at, status | 会员期限 |
| `trial_quotas` | id, user_id, device_id, total_count, used_count, remaining_count | 试用额度 |
| `tasks` | id, user_id, device_id, daily_limit, create_tag, greeting_text, status | 任务记录 |
| `task_results` | id, task_id, contact_id, result, message, trial_charged | 执行结果 |
| `contacts` | id, wechat_nickname, wechat_id, tag, status, remark | 联系人 |
| `admin_users` | id, username, password_hash, role, status | 管理员 |
| `admin_audit_logs` | id, admin_user_id, action, target_type, target_id, detail | 操作审计 |

---

## 八、重要文件修改记录

| 日期 | 文件 | 修改内容 |
|------|------|---------|
| 2026-06-24 | `PROJECT_PLAN.md` | 新增项目规划文档 |
| 2026-06-24 | `desktop/` | Tauri 初始搭建 + 登录 UI + 主界面 + 脚本联调 |
| 2026-06-24 | `server/` | FastAPI 初始搭建 + 12 表模型 + 迁移 + Auth/Device API |
| 2026-06-24 | `server/app/services/auth_service.py` | 验证码发送 + 登录 + 设备绑定 + 试用创建 |
| 2026-06-24 | `server/app/core/security.py` | SHA256 验证码哈希 + JWT token |
| 2026-06-24 | `server/app/core/deps.py` | get_current_user 依赖注入 |
| 2026-06-24 | `desktop/src/LoginPage.tsx` | 三标签登录 UI |
| 2026-06-24 | `desktop/src/MainPage.tsx` | 主界面 + 状态栏 |
| 2026-06-24 | `desktop/src/PaymentModal.tsx` | 充值弹窗（三栏套餐） |
| 2026-06-24 | `server/app/services/payment_service.py` | 支付回调 + 会员叠加 |
| 2026-06-25 | `server/app/services/task_service.py` | **新增**：任务校验/结果上报/结束任务 |
| 2026-06-25 | `server/app/api/tasks.py` | **新增**：3 个任务路由 |
| 2026-06-25 | `desktop/src/TaskPanel.tsx` | **新增**：任务面板组件 |
| 2026-06-25 | `desktop/src-tauri/src/lib.rs` | 重构为 start_task/stop_task + 事件流 |
| 2026-06-25 | `scripts/test_autobot.py` | 重写为 stdin JSON 通信 |
| 2026-06-25 | `server/app/schemas/admin.py` | **新增**：Admin 请求/响应 Schema |
| 2026-06-25 | `server/app/services/admin_service.py` | **新增**：Admin 业务逻辑 |
| 2026-06-25 | `server/app/api/admin.py` | **新增**：14 个 Admin API 端点 |
| 2026-06-25 | `server/app/core/deps.py` | 新增 get_current_admin 依赖注入 |
| 2026-06-25 | `server/app/seed.py` | 新增默认管理员 seed |
| 2026-06-25 | `admin/` | **新增**：独立管理后台 React 前端 |

---

## 九、Git 提交历史

```
xxxxxxxx (HEAD -> master) feat: complete stage 4 — admin panel, backend APIs and React frontend
95d08e0 feat: complete stage 3 — task panel, script integration, payment UI redesign
0bd937c docs: rewrite snapshot with comprehensive project status
cdc9d70 docs: translate snapshot to Chinese
49ca6ae docs: add project snapshot for session handoff
a14d772 chore: add desktop boilerplate files
ff8129f chore: update config and deps for stage 2
7e304e3 feat: add membership, trial, orders and payment system
f560185 feat: redesign login page with contemporary UI
93f9224 fix: skip device binding for test account in dev mode
fbc7686 feat: add fixed test account for dev
3411124 docs: update project management for stage 1 completion
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

---

## 十、开发环境

### 启动命令

```bash
# 后端
cd server
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --port 8001

# 桌面端
cd desktop
npm run tauri dev

# 管理后台
cd admin
npm run dev          # 浏览器打开 http://localhost:5174
```

### 测试账号

- **用户测试**：`test@friendauto.com` / 验证码 `888888`（跳过设备绑定）
- **管理员**：`admin` / `admin123`

### 常见问题

- 端口 8001 被占用：`Stop-Process -Id (Get-NetTCPConnection -LocalPort 8001).OwningProcess -Force`
- 重置数据库：删除 `server/friendauto.db`，重启后端自动重建
- 测试脚本独立运行：`echo '{"run_id":"test","contacts":[]}' | python scripts/test_autobot.py`

---

## 十一、风险与注意事项

1. ✅ 会员/试用判断不在客户端 — 服务端唯一可信来源
2. ✅ 支付密钥不在客户端 — 仅存服务端
3. ✅ 不依赖客户端轮询判断支付成功 — 以服务端回调验签为准
4. ✅ 卸载重装不重置试用次数 — 服务端保存
5. ✅ 幂等扣次 — `run_id + contact_id` 组合去重
6. ⚠️ 网络断开时应阻止启动新任务（待实现）
7. ⚠️ 需区分失败/无效/成功扣次规则，避免售后纠纷
8. ⚠️ 需要准备用户协议、隐私政策、数据删除机制
