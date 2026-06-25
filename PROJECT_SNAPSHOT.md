# FriendAuto — 项目状态快照

更新时间：2026-06-25
项目目录：`D:\FriendAuto`
远程仓库：`https://github.com/zzw-0912/AddFriendAuto.git`
分支：`master`（所有提交已推送）

---

## 一、项目目标

FriendAuto 是一款 Windows 桌面应用，客户通过 `.exe` 安装后，完成邮箱注册登录、设备绑定、会员充值或试用，然后在桌面端配置每日自动加好友任务。桌面端负责传参给已有 Python 自动化程序、启动程序、接收结果、上报服务器。

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
    │ 本地进程 (std::process::Command)
    ▼
Python 自动化程序 (scripts/test_autobot.py → 替换为真实脚本)
```

### 职责划分

| 层 | 职责 | 不负责 |
|---|---|---|
| **桌面端** | UI、登录、机器码采集、展示状态、启动脚本、展示日志 | 不判断会员有效/无效、不保存试用次数、不保存支付密钥 |
| **后端** | 注册登录、验证码校验、token 签发、设备绑定、会员判断、试用扣次、订单创建、支付回调 | — |
| **Python 脚本** | 接收参数、执行自动化、返回结果 | 不判断会员、充值、试用 |
| **后台管理（未开发）** | 用户管理、设备改绑、会员操作、订单查看、任务日志 | — |

### 安全设计

- 所有商业规则由服务端裁决，客户端只展示服务端返回的状态
- 支付密钥只存在于服务端
- 试用次数保存在服务端，卸载重装不能重置
- 机器码上传前做 SHA256 哈希，不上传明文硬件信息
- 关键接口（扣次、支付回调）做幂等处理
- 支付成功以服务端回调验签为准，不信任客户端轮询

---

## 三、已完成部分（共 17 次提交）

### 阶段 0：项目初始化与技术底座（7 次提交）

- `6068ccd` — 初始化 Git 仓库
- `94ff687` — 创建 Tauri 桌面工程
- `3cd467a` — 添加桌面端主界面 UI + 健康检查 + 脚本运行器
- `3b1cb68` — 初始化 FastAPI 后端 + SQLAlchemy 模型 + Alembic 迁移
- `d207f97` — 创建测试 Python 自动化脚本（打开记事本输入 123456）
- `7e7a0da` — 添加项目管理文档
- `3411124` — 更新阶段 1 完成状态

完成内容：
- Tauri v2 + React + TypeScript + Vite 工程搭建
- FastAPI 后端工程，SQLAlchemy ORM，SQLite 数据库（开发环境）
- 12 张数据表自动创建（users, email_codes, devices, memberships, plans, orders, payments, trial_quotas, tasks, task_results, contacts, admin_users, admin_audit_logs）
- 三档套餐数据种子（月卡 ¥29.9/30天、季卡 ¥79.9/90天、年卡 ¥299.9/365天）
- 测试 Python 脚本 `scripts/test_autobot.py`
- 健康检查接口 `GET /health`
- 桌面端运行测试脚本的 Rust 命令 `run_python_script`
- 一键启动脚本 `start_server.bat`、`start_desktop.bat`

### 阶段 1：账号、登录与设备绑定（5 次提交）

- `ce638e9` — 添加 auth 和 device API
- `4ab259c` — 添加机器码生成和 Token 持久化存储
- `0079f9d` — 添加登录页和主界面 UI
- `fbc7686` — 添加开发测试账号 `test@friendauto.com` / 固定验证码 `888888`
- `93f9224` — 测试账号跳过设备绑定

完成内容：
- `POST /auth/send-code` — 发送邮箱验证码（开发环境回显验证码）
- `POST /auth/login` — 验证码登录/注册（自动注册 + 自动设备绑定）
- `POST /auth/refresh` — 刷新 token
- `POST /devices/bind` — 绑定设备
- `GET /devices/current` — 当前设备信息
- 验证码 SHA256 哈希存储（因 passlib 与 bcrypt 5.x 冲突）
- 机器码通过 WMIC `csproduct get uuid` 获取（Rust `std::process::Command`）
- Token 持久化到 `%APPDATA%/FriendAuto/auth.json`
- 首次登录自动绑定设备，第二个设备登录返回 403
- 测试账号 `test@friendauto.com` 在 dev 模式下跳过设备绑定
- 桌面端三标签登录页（登录 / 注册 / 找回账号）

### 阶段 2：会员、试用与充值（3 次提交）

- `f560185` — 登录界面全新 UI 设计（根据 `样式.txt` 设计系统）
- `7e304e3` — 添加会员、试用、订单和支付系统
- `ff8129f` — 更新配置和依赖

完成内容：
- `GET /me/status` — 会员 + 试用状态查询
- `GET /plans` — 套餐列表（含 `price_yuan` 字段）
- `POST /orders` — 创建订单（订单号格式 `FA20260625...`）
- `GET /orders/{id}` — 查询订单
- `POST /payments/wechat/callback` — 模拟微信支付回调
- `POST /payments/alipay/callback` — 模拟支付宝支付回调
- 新用户自动创建 20 次试用额度
- 会员叠加：新周期从当前有效结束日开始
- 支付成功后自动激活/延长会员
- 桌面端：状态栏（VIP 到期日 / 试用剩余次数 + 充值按钮）
- 桌面端：充值弹窗（三档套餐卡片 + 模拟支付回调）
- Login UI 全面重设计（品牌面板、窗口标题栏、Toast、倒计时、表单验证）

### 文档与配置（2 次提交）

- `a14d772` — 添加 desktop 工程标配文件（.gitignore, README, package-lock.json, assets）
- `cdc9d70` — 创建并中文化 PROJECT_SNAPSHOT.md

---

## 四、待办事项

### 高优先级（Stage 3）
- [ ] `POST /tasks/start-check` — 任务开始前校验（会员/试用/设备/版本）
- [ ] `GET /contacts/search` — 按微信昵称和微信号筛选联系人
- [ ] `POST /tasks/{task_id}/results` — 上报单条执行结果（含幂等扣次）
- [ ] `POST /tasks/{task_id}/finish` — 结束任务
- [ ] `POST /tasks/{task_id}/logs` — 实时日志上传
- [ ] 桌面端主任务界面：每日限额、创建标签、打招呼语、开始/停止
- [ ] 桌面端日志展示（实时输出、成功数、失败数、无效数）
- [ ] 脚本通信协议对接（JSON stdin/stdout）
- [ ] 试用扣次逻辑：只有 `event = success` 才扣次，`run_id + contact_id` 幂等

### 中优先级（Stage 4）
- [ ] 后台管理：用户列表、详情、状态管理
- [ ] 后台管理：设备列表、解绑、改绑、备注
- [ ] 后台管理：会员开通、延期、冻结
- [ ] 后台管理：套餐价格配置
- [ ] 后台管理：订单列表、支付状态
- [ ] 后台管理：任务日志、扣次明细
- [ ] 后台管理：管理员操作审计日志
- [ ] 后台管理界面开发（React 或独立页面）

### 低优先级（Stage 5 — 上线前必须完成）
- [ ] 真实微信支付接入（验签、回调）
- [ ] 真实支付宝支付接入（验签、回调）
- [ ] 支付幂等处理（防止重复回调）
- [ ] PostgreSQL 生产环境切换
- [ ] Windows `.exe` 打包
- [ ] 客户端自动更新
- [ ] HTTPS 服务部署
- [ ] 接口限流（验证码、订单、任务）
- [ ] 客户端日志导出
- [ ] 网络断开时的错误提示和状态处理
- [ ] 代码签名
- [ ] 用户协议、隐私政策

---

## 五、关键决策

### 产品决策

| 决策 | 说明 |
|------|------|
| 邮箱验证码登录 | 无密码模式，6 位验证码，无需记住密码 |
| 一个账号一台设备 | 默认绑定一台设备，第二台拦截，需要管理员后台改绑 |
| 20 次试用额度 | 新用户自动获得 20 次成功加好友额度 |
| 按成功扣次 | 只有 `event = success` 才扣试用，失败/无效/异常不扣 |
| 会员覆盖试用 | 会员有效期内不扣试用次数 |
| 会员叠加 | 续费时新的有效期从当前有效期结束后开始 |
| 三档套餐 | 月卡 ¥29.9、季卡 ¥79.9、年卡 ¥299.9（价格由服务端配置） |

### 技术决策

| 决策 | 说明 |
|------|------|
| Tauri v2 + React + TypeScript | 桌面端技术栈，原生窗口 + Web UI |
| FastAPI + SQLAlchemy | 后端框架 + ORM |
| SQLite 开发 / PostgreSQL 生产 | 环境切换通过 `database_url` 配置 |
| SHA256 验证码哈希 | passlib 和 bcrypt 5.x 不兼容，改用 hashlib |
| WMIC csproduct UUID | Windows 机器码采集，不引入额外 Rust crate |
| 本地 JSON Token 存储 | `dirs_next::data_dir` + `auth.json`，```
在 `%APPDATA%/FriendAuto/auth.json` |
| `std::process::Command` | Rust 原生进程启动，不用 Tauri shell 插件 |
| 测试账号免绑定 | `test@friendauto.com` + `888888` 跳过设备绑定检查 |
| 支付回调 mock | 开发环境直接 `POST /payments/*/callback?order_no=...` |

---

## 六、数据库设计（12 张表）

| 表名 | 核心字段 | 用途 |
|------|---------|------|
| `users` | id, email, status, created_at, last_login_at | 用户账号 |
| `email_codes` | id, email, code_hash, expires_at, used_at | 验证码 |
| `devices` | id, user_id, machine_code_hash, status, bound_at, last_seen_at | 设备绑定 |
| `plans` | id, name, duration_days, price_cents, enabled | 套餐配置 |
| `orders` | id, order_no, user_id, plan_id, amount_cents, payment_channel, status | 订单 |
| `memberships` | id, user_id, starts_at, ends_at, status | 会员期限 |
| `trial_quotas` | id, user_id, device_id, total_count, used_count, remaining_count | 试用额度 |
| `tasks`（预创建） | id, user_id, device_id, daily_limit, create_tag, greeting_text, status | 任务记录 |
| `task_results`（预创建） | id, task_id, contact_id, result, trial_charged | 任务执行结果 |
| `contacts`（预创建） | id, wechat_nickname, wechat_id, tag, status | 联系人数据 |
| `admin_users`（预创建） | id, username, password_hash, role, status | 后台管理员 |
| `admin_audit_logs`（预创建） | id, admin_user_id, action, target_type, target_id | 操作审计 |

---

## 七、API 接口清单

| 方法 | 路径 | 说明 | 阶段 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 0 ✓ |
| POST | `/auth/send-code` | 发送邮箱验证码 | 1 ✓ |
| POST | `/auth/login` | 登录/注册（含设备绑定、试用额度创建） | 1 ✓ |
| POST | `/auth/refresh` | 刷新 token | 1 ✓ |
| POST | `/devices/bind` | 绑定设备 | 1 ✓ |
| GET | `/devices/current` | 当前设备信息 | 1 ✓ |
| GET | `/me/status` | 会员 + 试用状态 | 2 ✓ |
| GET | `/plans` | 套餐列表 | 2 ✓ |
| POST | `/orders` | 创建订单 | 2 ✓ |
| GET | `/orders/{id}` | 订单详情 | 2 ✓ |
| POST | `/payments/wechat/callback` | 微信支付回调（mock） | 2 ✓ |
| POST | `/payments/alipay/callback` | 支付宝支付回调（mock） | 2 ✓ |
| POST | `/tasks/start-check` | 任务前校验 | 3 |
| GET | `/contacts/search` | 搜索联系人 | 3 |
| POST | `/tasks/{id}/results` | 上报执行结果 | 3 |
| POST | `/tasks/{id}/finish` | 结束任务 | 3 |
| GET/PATCH | `/admin/*` | 后台管理接口 | 4 |

---

## 八、重要文件修改记录

| 日期 | 文件 | 修改内容 |
|------|------|---------|
| 2026-06-24 | `PROJECT_PLAN.md` | 新增完整项目规划文档（598 行） |
| 2026-06-24 | `PROJECT_MANAGEMENT.md` | 新增阶段 0 管理文档 |
| 2026-06-24 | `desktop/src-tauri/src/lib.rs` | 实现 Rust 命令：get_machine_code, run_python_script, save_token, load_token, clear_token |
| 2026-06-24 | `server/app/services/auth_service.py` | 实现 send_code, login（含自动注册、设备绑定、试用额度创建）, refresh |
| 2026-06-24 | `server/app/core/security.py` | 实现 hash_code（SHA256）、create_access_token（JWT） |
| 2026-06-24 | `server/app/core/deps.py` | 实现 get_current_user 依赖注入 |
| 2026-06-24 | `desktop/src/LoginPage.tsx` | 三标签登录 UI（登录/注册/找回账号）|
| 2026-06-24 | `desktop/src/MainPage.tsx` | 主界面（状态栏、健康检查、脚本运行器）|
| 2026-06-24 | `desktop/src/PaymentModal.tsx` | 充值弹窗（三档套餐 + 模拟支付回调）|
| 2026-06-24 | `server/app/services/payment_service.py` | 支付回调处理 + 会员叠加激活 |
| 2026-06-24 | `server/app/services/status_service.py` | 查询会员 + 试用状态 |
| 2026-06-24 | `server/app/services/order_service.py` | 创建订单（UUID 订单号）、查询订单 |
| 2026-06-24 | `server/app/core/config.py` | 配置：database_url, jwt secret, smtp, 支付密钥 |
| 2026-06-24 | `server/app/seed.py` | 数据库初始化 + 三档套餐种子数据 |
| 2026-06-25 | `PROJECT_SNAPSHOT.md` | 创建并中文化项目快照 |

---

## 九、开发环境

### 启动命令

```bash
# 后端
cd server
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --port 8001

# 桌面端
cd desktop
npm run tauri dev
```

### 测试账号

- 邮箱：`test@friendauto.com`
- 验证码：`888888`
- 特点：开发环境自动跳过设备绑定，不需要真实 SMTP

### 常见问题

- 端口 8001 被占用：`Stop-Process -Id (netstat -ano | findstr ':8001' | Select-Object -First 1) -replace '.*\s+(\d+)$','$1' -Force`
- 重置数据库：删除 `server/friendauto.db`，重启后端自动重建

---

## 十、脚本通信协议

### 桌面端 → 脚本

```json
{
  "run_id": "task_001",
  "daily_limit": 20,
  "create_tag": true,
  "greeting_text": "你好，我是XXX",
  "contacts": [
    { "contact_id": "contact_001", "wechat_nickname": "张三", "wechat_id": "wxid_001" }
  ]
}
```

### 脚本 → 桌面端

```json
{ "run_id": "task_001", "contact_id": "contact_001", "event": "success", "message": "添加成功", "timestamp": "2026-06-24T12:00:00+08:00" }
```

事件类型：`started` | `progress` | `success` | `invalid` | `failed` | `finished` | `error`

扣次规则：只有 `event = success` 才扣试用次数，`run_id + contact_id` 组合幂等。

---

## 十一、风险点

- 不能把会员/试用判断放在客户端
- 不能把支付密钥放在客户端
- 不能只依赖客户端轮询判断支付成功
- 不能重置试用次数（卸载重装也不重置）
- 不能重复扣次（幂等必须做好）
- 网络断开时不能启动新任务
- 必须区分失败/无效/成功，否则售后纠纷

---

## 十二、下一阶段（Stage 3）

立即需要开发的内容：

1. **后端接口**（4 个）：
   - `POST /tasks/start-check` — 校验会员/试用/设备/版本状态
   - `GET /contacts/search` — 模糊搜索联系人
   - `POST /tasks/{task_id}/results` — 上报单条结果（含幂等扣次）
   - `POST /tasks/{task_id}/finish` — 结束任务

2. **桌面端主界面改造**：
   - 替换当前测试区为真实任务面板
   - 输入：每日限额、创建标签开关、打招呼语文本框
   - 操作：开始/停止按钮
   - 输出：实时日志列表、成功/失败/无效计数器

3. **脚本集成**：
   - 实现桌面端 ↔ 脚本的 JSON stdin/stdout 通信
   - 试用扣次对接（通过服务端接口）
   - 完成测试脚本联调后替换为真实脚本
