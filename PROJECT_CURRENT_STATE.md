# FriendAuto 当前项目状态

更新时间：2026-06-27
项目目录：`D:\FriendAuto`
远程仓库：`https://github.com/zzw-0912/AddFriendAuto.git`
当前分支：`master`

---

## 1. 项目概览

FriendAuto 是一个 Windows 桌面自动化产品，目标流程是：

`邮箱注册/登录 -> 设备绑定 -> 试用或会员充值 -> 配置自动加好友任务 -> 本地 Python 脚本执行 -> 结果回传服务端`

当前项目由 3 个主要部分组成：

- `desktop/`：Tauri v2 + React + TypeScript 桌面客户端
- `server/`：FastAPI + SQLAlchemy 后端
- `admin/`：独立 React 管理后台

---

## 2. 关键决策

### 2.1 产品决策

| 决策 | 当前方案 |
|---|---|
| 登录方式 | 邮箱 + 密码登录；注册和找回密码通过邮箱验证码 |
| 设备策略 | 一台设备可绑定多个账号；一个账号只能绑定一台设备 |
| 试用规则 | 新用户自动获得 20 次试用，仅 `success` 扣次 |
| 会员规则 | 会员有效期内不扣试用；续费叠加到当前到期时间后 |
| 套餐档位 | 月卡 / 季卡 / 年卡，价格由后台管理 |
| 套餐决定任务卡片数 | 月卡/试用=1 个任务卡片、季卡=2 个、年卡=3 个 |
| 侧边栏 | 仅保留底部导航（客服、反馈、我的、设置），删除功能导航项 |
| 客户端定位 | 负责 UI、登录态、机器码、脚本拉起、结果展示和上报，不裁决商业规则 |

### 2.2 技术决策

| 决策 | 当前方案 |
|---|---|
| 桌面端 | Tauri v2 + React + TypeScript + Vite |
| 后端 | FastAPI + SQLAlchemy |
| 数据库 | SQLite 开发，PostgreSQL 预留生产切换 |
| 密码存储 | bcrypt |
| 验证码存储 | SHA256 哈希 |
| 机器码采集 | Windows `wmic csproduct get uuid` |
| 本地登录态 | `%APPDATA%/FriendAuto/auth.json` |
| 脚本通信 | Rust `Command` + stdin JSON + stdout 逐行 JSON + Tauri `emit/listen` |
| 支付现状 | 已有订单/回调流程，仍为 mock，未接真实支付 |
| 标题栏 | 使用 OS 原生标题栏（`decorations: true`），无自定义按钮 |
| 窗口尺寸 | 登录页 900×720，主页面 `min(1370px, ...)` × `min(1032px, ...)` |
| 会员充值 | "联系工作人员充值"→弹出微信二维码浮层，不经过 API 支付流程 |

### 2.3 架构边界

- 服务端是会员、试用、设备绑定、订单、支付状态的唯一可信来源
- 桌面端不保存支付密钥，不做会员或试用判断
- Python 脚本只执行自动化，不感知会员和支付逻辑
- 管理后台用于用户、设备、套餐、订单、任务和审计运营

---

## 3. 已完成部分

### 阶段 0：项目初始化与技术底座 ✅

- Tauri v2 + React + TypeScript + Vite 桌面工程搭建
- FastAPI 后端工程 + SQLAlchemy ORM + SQLite 开发数据库
- 13 张数据表自动创建 + 三档套餐种子数据
- 测试 Python 脚本 `scripts/test_autobot.py`
- 健康检查接口 `GET /health` + 一键启动脚本

### 阶段 1：账号、登录与设备绑定 ✅

- `POST /auth/send-code` — 邮件验证码发送（QQ邮箱 SMTP 真实发送）
- `POST /auth/login` — 邮箱+密码登录（自动设备绑定）
- `POST /auth/register` — 邮箱+密码+验证码注册
- `POST /auth/reset-password` — 验证码+新密码重置
- `POST /auth/refresh` — Token 刷新
- `POST /devices/bind` / `GET /devices/current` — 设备绑定与查询
- 桌面端三标签登录页（登录/注册/找回密码）

### 阶段 2：会员、试用与充值 ✅

- `GET /me/status` — 会员 + 试用状态查询
- `GET /plans` — 套餐列表
- `POST /orders` / `GET /orders/{id}` — 订单创建与查询
- `POST /payments/*/callback` — 模拟微信/支付宝支付回调
- 新用户自动创建 20 次试用额度 + 会员叠加逻辑
- 桌面端充值弹窗（三栏套餐卡片 + 联系工作人员充值）
- 登录 UI 全面重设计（设计系统复刻）

### 阶段 3：主界面与自动化脚本联调 ✅

- `POST /tasks/start-check` — 任务前校验
- `GET /contacts/search` — 联系人筛选
- `POST /tasks/{id}/results` — 结果上报（幂等扣次）
- `POST /tasks/{id}/finish` — 结束任务
- 桌面端任务面板 `TaskPanel.tsx`（配置/日志/计数器）
- Rust 脚本集成：stdin JSON + BufReader + Tauri 事件流
- 充值弹窗 `PaymentModal.tsx` 全面重设计

### 阶段 4：后台管理 ✅

- 后管 API：管理员登录、用户/设备/套餐/订单/任务/审计管理（14 个端点）
- 管理员独立 JWT 认证（`get_current_admin`）
- 默认管理员 `admin` / `admin123`
- 操作审计日志自动记录
- 独立 React 管理前端（7 个页面）

### 阶段 5 先行 — 侧边栏精简 + 套餐等级任务卡片 ✅

- 侧边栏删除上半部分导航，仅保留底部（客服、反馈、我的、设置）
- `Membership` 模型新增 `plan_id`，支付时写入
- `/me/status` 返回 `plan_id`，前端据此渲染 N 个任务卡片
- 提取 `TaskCard.tsx` 可复用组件，每个卡片独立运行

### 个人资料与设置页 ✅

- `POST /me/profile` 聚合接口（用户信息 + 统计 + 推荐码）
- `ProfilePage.tsx`：账号信息、会员状态、累计数据、推荐码及二维码
- `SettingsPage.tsx`：任务默认配置、设备信息、修改密码、快捷入口

### 网络异常处理 ✅（本会话新增）

- `useNetworkStatus.ts`：单例模式 Hook，监听 `navigator.onLine` 和 `online`/`offline` 事件
- `OfflineBanner.tsx`：断网时在内容区顶部显示红色警告横幅（带淡入动画）
- `TaskPanel.tsx`：断网时开始按钮 disabled，启动任务前检查网络并日志提示
- `api.ts`：统一 API 工具层（`apiGet`/`apiPost`/`readErrorDetail`）+ `NetworkError`/`AuthError` 异常类
- 消除 `readErrorDetail` 重复代码（ProfilePage / SettingsPage 共用）

---

## 4. 当前待办

### 4.1 上线前高优先级

1. PostgreSQL 生产环境切换（需梳理 SQLite 兼容补列逻辑）
2. Windows `.exe` 打包（Tauri build）
3. 客户端自动更新（Tauri updater）
4. HTTPS 服务部署（Nginx + SSL）
5. 接口限流（验证码/订单/任务）
6. 客户端日志导出
7. 网络断开时的错误提示和状态处理（**已完成** — 含离线横幅 + 按钮禁用 + 启动拦截）
8. 代码签名（减少 Windows Defender 拦截）
9. 异常告警和服务器监控
10. 安装包在干净 Windows 环境验证

### 4.2 产品和体验待补

1. 桌面端真实联系人导入 / 筛选链路仍较弱
2. 自动更新、日志导出、安装包签名尚未落地
3. 协议与隐私文档、正式上线法务信息未补齐
4. 侧边栏路由挂载（当前导航项为 UI 占位）
5. 轮播横幅 JS 交互（自动轮播 + 指示器）

### 4.3 脚本集成待替换

- 当前 `scripts/test_autobot.py` 仍是测试脚本
- 未来需替换为真实业务自动化脚本，保持 stdin/stdout JSON 协议不变

### 4.4 延期决定

- 真实微信/支付宝支付接入暂不进行，后续有需求再完善（对应的支付幂等也延后）

---

## 5. 架构思路

### 5.1 总体结构

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

### 5.2 脚本通信流程

```
[前端] invoke("start_task", {configJson})
  → [Rust] spawn python → stdin.write(config)
  → [Python] 读取 stdin → 处理联系人 → stdout JSON 逐行
  → [Rust] BufReader 逐行读取 → emit("script-event", line)
  → [前端] listen("script-event") → 解析 → 更新日志/计数器
  → 每条 success 事件 → POST /tasks/{id}/results (幂等扣次)
  → [用户点击停止] → invoke("stop_task") → kill 子进程
```

### 5.3 当前分层职责

| 层 | 职责 |
|---|---|
| `desktop/src` | UI、登录态、机器码、本地偏好、脚本状态展示 |
| `desktop/src-tauri` | 本地命令桥接、token 落盘、脚本进程管理 |
| `server/app/api` | 路由层 |
| `server/app/services` | 业务逻辑层 |
| `server/app/models` / `schemas` | 数据模型与接口契约 |
| `admin/src` | 运营后台界面 |

---

## 6. 数据表设计（13 张表）

| 表名 | 核心字段 | 用途 |
|------|---------|------|
| `users` | id, email, **password_hash**, **referral_code**, status | 用户账号 |
| `email_codes` | id, email, code_hash(SHA256), expires_at | 验证码 |
| `devices` | id, user_id, machine_code_hash, status, remark | 设备绑定 |
| `plans` | id, name, duration_days, price_cents, enabled | 套餐配置 |
| `orders` | id, order_no, user_id, plan_id, amount_cents, status | 订单 |
| `memberships` | id, user_id, **plan_id**, starts_at, ends_at, status | 会员期限 |
| `trial_quotas` | id, user_id, total_count, used_count, remaining_count | 试用额度 |
| `tasks` | id, user_id, device_id, daily_limit, status | 任务记录 |
| `task_results` | id, task_id, contact_id, result, message, trial_charged | 执行结果 |
| `contacts` | id, wechat_nickname, wechat_id, tag, status | 联系人 |
| `payments` | id, order_id, channel, transaction_id, status | 支付记录 |
| `admin_users` | id, username, password_hash, role, status | 管理员 |
| `admin_audit_logs` | id, admin_user_id, action, target_type, detail | 操作审计 |

---

## 7. API 接口清单

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/send-code` | 发送邮箱验证码（60 秒频率限制） |
| POST | `/auth/login` | 邮箱+密码登录（自动设备绑定） |
| POST | `/auth/register` | 邮箱+密码+验证码注册 |
| POST | `/auth/reset-password` | 验证码+新密码重置 |
| POST | `/auth/refresh` | 刷新 token |

### 设备
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/devices/bind` | 绑定设备 |
| GET | `/devices/current` | 当前设备信息 |

### 会员与支付
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/me/status` | 会员+试用状态 |
| GET | `/me/profile` | 个人资料+统计+推荐码 |
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
| POST | `/tasks/{id}/results` | 上报执行结果（幂等） |
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

## 8. 重要文件修改记录

### 8.1 本次会话改动（2026-06-27 — 网络异常处理）

| 文件 | 操作 | 说明 |
|------|------|------|
| `desktop/src/useNetworkStatus.ts` | **新增** | 网络状态监测 Hook（单例，监听 online/offline 事件） |
| `desktop/src/api.ts` | **新增** | 统一 API 工具层（apiGet/apiPost/readErrorDetail + 异常类） |
| `desktop/src/OfflineBanner.tsx` | **新增** | 断网红色警告横幅组件 |
| `desktop/src/MainPage.tsx` | 修改 | 集成 OfflineBanner + useNetworkStatus |
| `desktop/src/MainPage.css` | 修改 | 新增 OfflineBanner 样式（红色背景 + 淡入动画） |
| `desktop/src/TaskPanel.tsx` | 修改 | 启动前检查网络、断网禁用按钮、日志提示 |
| `desktop/src/PaymentModal.tsx` | 修改 | 静默 catch 加注释说明 |
| `desktop/src/ProfilePage.tsx` | 修改 | readErrorDetail 共用 api.ts |
| `desktop/src/SettingsPage.tsx` | 修改 | readErrorDetail 共用 api.ts |

### 8.2 上次会话改动（个人资料 + 设置页）

| 文件 | 操作 | 说明 |
|------|------|------|
| `server/app/api/profile.py` | **新增** | `/me/profile` 聚合接口 |
| `server/app/services/profile_service.py` | **新增** | 个人资料统计聚合 |
| `server/app/schemas/profile.py` | **新增** | Profile Schema |
| `server/app/models/user.py` | 修改 | 新增 `referral_code` 字段 |
| `server/app/services/auth_service.py` | 修改 | 注册时生成推荐码 |
| `desktop/src/ProfilePage.tsx` | **新增** | 用户资料页 |
| `desktop/src/SettingsPage.tsx` | **新增** | 设置页 |
| `desktop/src/types.ts` | **新增** | 共享类型和任务默认值常量 |
| `desktop/src/useSendCode.ts` | **新增** | 验证码发送和倒计时复用逻辑 |
| `desktop/src/MainPage.css` | 修改 | 新增 profile/settings 页面样式 |

---

## 9. 项目文件结构

```
D:\FriendAuto/
├── desktop/                          # Tauri v2 桌面客户端
│   ├── src/
│   │   ├── App.tsx                   # 应用入口（路由 + token 恢复）
│   │   ├── App.css                   # CSS 设计系统 + 登录页样式
│   │   ├── LoginPage.tsx             # 登录/注册/找回密码三标签
│   │   ├── MainPage.tsx              # 主页面（侧边栏 + 状态栏 + 内容区）
│   │   ├── MainPage.css              # 主页全部样式（~1780 行）
│   │   ├── TaskCard.tsx              # 可复用任务卡片（包裹 TaskPanel）
│   │   ├── TaskPanel.tsx             # 任务面板（配置/日志/计数器）
│   │   ├── PaymentModal.tsx          # 充值弹窗（联系工作人员）
│   │   ├── ProfilePage.tsx           # "我的" 页面
│   │   ├── SettingsPage.tsx          # 设置页面
│   │   ├── FeedbackModal.tsx         # 意见反馈弹窗
│   │   ├── QRCodeModal.tsx           # 微信二维码浮层
│   │   ├── OfflineBanner.tsx         # 断网横幅 ***NEW***
│   │   ├── useNetworkStatus.ts       # 网络状态 Hook ***NEW***
│   │   ├── useSendCode.ts            # 验证码倒计时 Hook
│   │   ├── api.ts                    # 统一 API 工具 ***NEW***
│   │   ├── types.ts                  # 共享类型 + 默认值
│   │   ├── index.css / main.tsx      # 全局 reset + React 入口
│   │   └── vite-env.d.ts
│   ├── src-tauri/
│   │   ├── src/lib.rs                # Rust Tauri 命令（机器码/token/脚本进程）
│   │   └── src/main.rs               # 入口
│   ├── package.json / vite.config.ts
│   └── tauri.conf.json
├── server/                           # FastAPI 后端
│   ├── app/
│   │   ├── main.py                   # FastAPI 应用入口
│   │   ├── seed.py                   # 建表 + 种子数据 + 兼容补列
│   │   ├── core/                     # config/database/security/deps
│   │   ├── models/                   # 13 个 ORM 模型
│   │   ├── schemas/                  # Pydantic schema
│   │   ├── services/                 # 业务逻辑层
│   │   └── api/                      # 路由层
│   ├── .env                          # SMTP + 密钥（gitignored）
│   └── friendauto.db                 # SQLite 数据库
├── admin/                            # 管理后台 React 前端
│   └── src/                          # 7 个管理页面
├── scripts/
│   └── test_autobot.py               # 测试自动化脚本
├── start_server.bat / start_desktop.bat
├── PROJECT_PLAN.md                   # 原始规划
├── PROJECT_MANAGEMENT.md             # 阶段推进记录
├── PROJECT_SNAPSHOT.md               # 跨会话交接快照
├── SESSION_STATE.md                  # 上次详细会话快照
├── SESSION_SUMMARY.md                # 会话摘要
├── PROJECT_SUMMARY.md                # 早期总结
└── PROJECT_CURRENT_STATE.md          # ← 当前文档，优先阅读
```

---

## 10. 启动与续接方式

### 10.1 常用启动命令

```powershell
# 后端（端口 8001）
cd D:\FriendAuto\server
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 桌面端
cd D:\FriendAuto\desktop
npm run tauri dev

# 管理后台（端口 5173）
cd D:\FriendAuto\admin
npm run dev
```

### 10.2 测试账号

- 用户测试：`test@friendauto.com` / 密码或验证码 `888888`（跳过密码+设备绑定）
- 管理员：`admin` / `admin123`

### 10.3 常用操作

- 重置数据库：删除 `server/friendauto.db`，重启后端自动重建
- 脚本独立测试：`echo '{"run_id":"test","contacts":[]}' | python scripts/test_autobot.py`
- 端口被占：`netstat -ano | findstr ':8001'`
- TypeScript 检查：在 `desktop/` 下执行 `npx tsc --noEmit`

### 10.4 下次新会话建议入口

1. 先读 **`PROJECT_CURRENT_STATE.md`**（当前文档）
2. 再看 `git status` 和 `git log --oneline -n 10`
3. 若做桌面端相关功能，从 `desktop/src/MainPage.tsx` 和 `desktop/src-tauri/src/lib.rs` 切入
4. 若做后端业务，从 `server/app/main.py`、`api/`、`services/` 三层切入

---

## 11. 当前风险与注意事项

1. 真实支付暂不接入，当前充值流程依赖微信二维码浮层（联系工作人员）
2. SQLite 兼容补列逻辑越来越多，后续切 PostgreSQL 时要认真梳理迁移脚本
3. 桌面端已有较多状态入口，注意不要把 `MainPage.tsx` 做得过重
4. Python 脚本仍是测试替身，真正接业务脚本时要保持 JSON 协议兼容
5. 当前 master 上存在持续演进的本地修改，提交前需统一打包入库
6. 网络异常处理已完善（离线横幅 + 按钮禁用 + 启动拦截），服务端不可达时不会再静默工作
