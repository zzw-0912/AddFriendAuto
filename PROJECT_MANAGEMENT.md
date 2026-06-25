# FriendAuto 项目管理文档

> 用于阶段交接，记录当前阶段关键决策、已完成部分、待办事项、重要文件修改记录和架构思路。

---

## 当前阶段：阶段 3 — 主界面与自动化脚本联调

### 状态：已完成

---

## 关键决策记录

| 编号 | 决策 | 选项 | 最终选择 | 原因 |
|------|------|------|----------|------|
| 1 | 数据库 | PostgreSQL / SQLite | 开发阶段用 SQLite，部署时切 PostgreSQL | 简化本地开发环境，SQLAlchemy 支持无缝切换 |
| 2 | Rust 安装失败处理 | 安装 / 跳过 | 重新安装 stable 工具链 | Tauri 必需 Rust 环境 |
| 3 | 脚本执行方式 | Tauri shell plugin / Rust Command | Rust `Command` + `invoke` | 更可靠，无需额外 shell 权限配置 |
| 4 | 测试脚本依赖 | pygetwindow+keyboard / 简化版 | 纯 stdin/stdout JSON | Stage 3 改为标准 IO 通信，不再依赖 GUI 库 |
| 5 | 项目结构 | monorepo | 单仓库，desktop/ + server/ + scripts/ 分离 | 方便管理，前后端独立开发部署 |
| 6 | 桌面端技术栈 | Tauri v2 + React + TypeScript + Vite | 按规划执行 | 符合项目规划文档要求 |
| 7 | 验证码哈希算法 | passlib+bcrypt / hashlib.sha256 | hashlib.sha256 | passlib 与 bcrypt 5.x 不兼容，验证码短时效无需 bcrypt |
| 8 | 登录设备绑定时机 | 登录时自动绑 / 手动绑定 | 登录时自动绑定 + 手动绑定 API | 简化用户体验，首次登录即完成绑定 |
| 9 | 机器码生成方式 | machine-uid crate / WMIC / sysinfo | WMIC csproduct UUID | 无需额外 Rust 依赖，Windows 原生支持 |
| 10 | Token 持久化 | Tauri store plugin / 本地 JSON 文件 | 本地 JSON 文件 (`dirs_next::data_dir`) | 最简单可靠，不依赖额外插件 |
| 11 | 脚本通信方式 | CLI 参数 / stdin JSON | stdin 传入 JSON 配置 | 支持复杂结构化参数，无需 shell 转义 |
| 12 | 实时日志传输 | 轮询 / Tauri 事件流 | Tauri 事件流 (`emit` + `listen`) | 零延迟，无需轮询，原生支持 |
| 13 | 子进程管理 | 不管理 / Mutex<Child> | Tauri State `Mutex<Option<Child>>` | 支持 start/stop，进程句柄线程安全 |
| 14 | 充值弹窗设计 | 简单列表 / 三栏套餐卡片 | 三栏套餐卡片 + 支付方式选择 | 根据 `样式.txt` 设计系统复刻，提升转化率 |
| 15 | 试用扣次触发 | 前端决策 / 服务端决策 | 服务端决策（report_result 内判断） | 客户端不可信，服务端是唯一可信来源 |

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
  - 会员/试用状态展示 + 充值按钮

### 阶段 2 完成清单

- [x] `GET /me/status` — 会员 + 试用状态查询
- [x] `GET /plans` — 套餐列表（含 `price_yuan`）
- [x] `POST /orders` — 创建订单（订单号格式 `FA20260625...`）
- [x] `GET /orders/{id}` — 查询订单
- [x] `POST /payments/wechat/callback` — 模拟微信支付回调
- [x] `POST /payments/alipay/callback` — 模拟支付宝支付回调
- [x] 新用户自动创建 20 次试用额度
- [x] 会员叠加：新周期从当前有效结束日开始
- [x] 支付成功后自动激活/延长会员
- [x] 桌面端状态栏：VIP 到期日 / 试用剩余次数 + 充值按钮
- [x] 登录 UI 全面重设计（品牌面板、窗口标题栏、Toast、倒计时、表单验证）

### 阶段 3 完成清单

- [x] `POST /tasks/start-check` — 任务前校验接口
  - 校验会员是否有效或试用次数是否充足
  - 校验通过后自动创建 Task 记录并返回 task_id
  - 返回完整的会员和试用状态信息
- [x] `GET /contacts/search?q=xxx` — 联系人筛选接口
  - 按微信昵称和微信号模糊搜索
  - 返回前 50 条活跃联系人
- [x] `POST /tasks/{id}/results` — 结果上报接口（幂等）
  - 仅 `event = success` 且无活跃会员时扣试用次数
  - `run_id + contact_id` 组合幂等，重复上报不扣次
  - 返回 `{charged, duplicate}` 标识
- [x] `POST /tasks/{id}/finish` — 结束任务
  - 标记 status = finished，记录 finished_at
- [x] 桌面端任务面板 `TaskPanel.tsx`
  - 任务配置：每日限额、创建标签开关、打招呼语文本框
  - 开始/停止按钮
  - 实时日志滚动输出（颜色区分 success/failed/invalid/error）
  - 计数器：成功数、失败数、无效数
  - 状态展示：会员到期时间、剩余试用次数
- [x] Rust 脚本集成
  - `start_task`：stdin 传 JSON 配置，BufReader 逐行读 stdout，emit Tauri 事件
  - `stop_task`：kill 子进程
  - Tauri State `Mutex<Option<Child>>` 管理进程句柄
- [x] 测试脚本重写
  - stdin 读取 JSON 配置
  - 模拟 3 个联系人（2 成功 + 1 失败）
  - 逐行 JSON stdout 输出
  - 1 秒间隔模拟处理延时
- [x] 充值弹窗全面重设计（PaymentModal.tsx）
  - 三栏套餐卡片（月卡/季卡/年卡）
  - 推荐标识 + 功能列表
  - 微信支付 / 支付宝选择
  - 跳过试用链接
  - 价格从服务端 `/plans` API 获取
  - 试用剩余次数从用户状态获取

### 验证结果

```
# 后端集成测试
POST /tasks/start-check       → {"can_start":true, "task_id":1, ...}
POST /tasks/1/results         → {"charged":false, "duplicate":false}  (会员有效时不扣次)
POST /tasks/1/results (重复)  → {"charged":false, "duplicate":true}
POST /tasks/1/finish          → {"id":1, "status":"finished", ...}
GET  /contacts/search?q=test  → []

# Tauri 编译
cargo check → 编译成功 (0 warnings)

# TypeScript 编译
npx tsc --noEmit → 通过 (0 errors)

# Python 后端模块
所有 Stage 3 模块导入正常

# 桌面端
- start_task: stdin JSON → Python 子进程 → stdout 事件流 → 前端日志
- stop_task: 子进程终止
- TaskPanel: 配置/日志/计数器全部渲染
- PaymentModal: 三栏卡片 + 支付方式选择 + 跳过试用
```

---

## 项目结构

```
D:\FriendAuto/
├── desktop/                    # Tauri 桌面端工程
│   ├── src/                    # React + TypeScript 前端
│   │   ├── App.tsx             # 应用入口（登录/主界面路由）
│   │   ├── App.css             # 设计系统 + 登录页样式
│   │   ├── main.tsx            # React 入口
│   │   ├── index.css           # 全局样式
│   │   ├── LoginPage.tsx       # 登录/注册/找回页面
│   │   ├── MainPage.tsx        # 主页面（状态栏 + 任务面板 + 充值弹窗）
│   │   ├── MainPage.css        # 主页面 + 任务面板 + 支付弹窗样式
│   │   ├── TaskPanel.tsx       # 任务面板（配置/日志/计数器）
│   │   └── PaymentModal.tsx    # 充值弹窗（三栏套餐/支付选择）
│   ├── src-tauri/              # Tauri Rust 后端
│   │   ├── src/
│   │   │   ├── lib.rs          # Tauri 命令：机器码/Token/start_task/stop_task
│   │   │   └── main.rs         # 启动入口
│   │   ├── Cargo.toml          # Rust 依赖
│   │   ├── tauri.conf.json     # Tauri 配置
│   │   └── capabilities/       # 权限配置
│   ├── package.json
│   └── vite.config.ts
├── server/                     # FastAPI 后端工程
│   ├── app/
│   │   ├── main.py             # FastAPI 应用入口（路由注册）
│   │   ├── seed.py             # 数据库初始化 + 种子数据
│   │   ├── core/
│   │   │   ├── config.py       # 配置（pydantic-settings）
│   │   │   ├── database.py     # SQLAlchemy 引擎 + Session
│   │   │   ├── security.py     # JWT + SHA256 哈希
│   │   │   └── deps.py         # 依赖注入（get_current_user）
│   │   ├── api/
│   │   │   ├── health.py       # 健康检查
│   │   │   ├── auth.py         # 认证路由
│   │   │   ├── devices.py      # 设备路由
│   │   │   ├── status.py       # 会员/试用状态
│   │   │   ├── plans.py        # 套餐列表
│   │   │   ├── orders.py       # 订单创建/查询
│   │   │   ├── payments.py     # 支付回调 mock
│   │   │   ├── tasks.py        # 任务路由（start-check/results/finish）
│   │   │   └── contacts.py     # 联系人搜索
│   │   ├── models/             # SQLAlchemy ORM 模型（12 张表）
│   │   ├── schemas/            # Pydantic schema
│   │   └── services/           # 业务逻辑层
│   ├── alembic/                # 数据库迁移
│   ├── alembic.ini
│   ├── .env                    # 环境变量
│   └── friendauto.db           # SQLite 数据库文件
├── scripts/
│   └── test_autobot.py         # 测试自动化脚本（stdin JSON + stdout 逐行事件）
├── start_server.bat            # 后端启动脚本
├── start_desktop.bat           # 桌面端启动脚本
├── PROJECT_PLAN.md             # 项目规划文档
├── PROJECT_MANAGEMENT.md       # 项目管理文档（本文件）
└── PROJECT_SNAPSHOT.md         # 项目状态快照
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
| 2026-06-24 | `server/app/services/payment_service.py` | 支付回调处理 + 会员叠加 | 新增 |
| 2026-06-24 | `server/app/services/status_service.py` | 查询会员 + 试用状态 | 新增 |
| 2026-06-24 | `server/app/services/order_service.py` | 创建订单 + 查询 | 新增 |
| 2026-06-24 | `server/app/api/orders.py` | 订单路由 | 新增 |
| 2026-06-24 | `server/app/api/payments.py` | 支付回调路由 | 新增 |
| 2026-06-24 | `server/app/api/plans.py` | 套餐列表路由 | 新增 |
| 2026-06-24 | `server/app/api/status.py` | 状态查询路由 | 新增 |
| 2026-06-25 | `server/app/schemas/task.py` | 新增任务 Schema | Stage 3 新增 |
| 2026-06-25 | `server/app/schemas/contact.py` | 新增联系人 Schema | Stage 3 新增 |
| 2026-06-25 | `server/app/services/task_service.py` | 新增任务业务逻辑 | start_check/report_result/finish |
| 2026-06-25 | `server/app/services/contact_service.py` | 新增联系人搜索服务 | |
| 2026-06-25 | `server/app/api/tasks.py` | 新增任务路由 | 3 个端点 |
| 2026-06-25 | `server/app/api/contacts.py` | 新增联系人路由 | 1 个端点 |
| 2026-06-25 | `server/app/main.py` | 注册 contacts/tasks 路由 | |
| 2026-06-25 | `server/app/models/task_result.py` | 新增 message 字段 | |
| 2026-06-25 | `desktop/src/TaskPanel.tsx` | 新增任务面板组件 | Stage 3 核心 |
| 2026-06-25 | `desktop/src-tauri/src/lib.rs` | 重构为 start_task/stop_task | 事件流通信 |
| 2026-06-25 | `desktop/src/MainPage.tsx` | 集成 TaskPanel | 替换测试区 |
| 2026-06-25 | `desktop/src/MainPage.css` | 新增任务面板/支付弹窗样式 | |
| 2026-06-25 | `desktop/src/PaymentModal.tsx` | 全面重设计 | 三栏卡片、支付选择、跳过试用 |
| 2026-06-25 | `scripts/test_autobot.py` | 重写为 stdin JSON | 多联系人模拟 |

---

## 待办事项

### 阶段 4 — 高优先级（后台管理）
- [ ] 后台管理界面开发（React 独立页面）
- [ ] 用户管理：列表、详情、状态管理
- [ ] 设备管理：列表、解绑、改绑、备注
- [ ] 会员管理：开通、延期、冻结、恢复
- [ ] 套餐价格配置
- [ ] 订单列表、支付状态查询
- [ ] 任务日志、扣次明细查询
- [ ] 管理员操作审计日志

### 阶段 5 — 中优先级
- [ ] 真实微信支付接入（验签、回调）
- [ ] 真实支付宝支付接入（验签、回调）
- [ ] 支付幂等处理
- [ ] PostgreSQL 生产环境切换
- [ ] Windows `.exe` 打包
- [ ] 客户端自动更新
- [ ] HTTPS 服务部署
- [ ] 接口限流
- [ ] 客户端日志导出
- [ ] 代码签名
- [ ] 用户协议、隐私政策

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
│  │  - get_machine_code / save_token / load_token       │ │
│  │  - start_task / stop_task (子进程管理)               │ │
│  │  - emit("script-event") 通信                        │ │
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
│              Python 自动化程序 (外部进程)                   │
│   stdin JSON → 执行微信自动化 → stdout JSON 逐行          │
│  通信方式：std::process::Command + stdin/stdout           │
└──────────────────────────────────────────────────────────┘
```

### 关键架构原则

1. **服务端是唯一可信来源**：会员状态、试用次数、设备绑定均由服务端裁决
2. **进程隔离**：桌面端与自动化程序通过 JSON over stdin/stdout 通信
3. **幂等处理**：关键接口（扣次、支付回调）必须幂等
4. **不可篡改**：客户端不保存真实会员判断结果，不保存支付密钥
5. **可切换数据库**：SQLAlchemy ORM 屏蔽数据库差异，开发 SQLite → 部署 PostgreSQL
6. **事件驱动日志**：Rust BufReader + Tauri emit 事件，前端 listen 实时渲染，零轮询

### 脚本通信流程

```
[前端] invoke("start_task", {configJson})
  │
  ▼
[Rust] spawn python → stdin.write(config)
  │
  ▼
[Python] 读取 stdin → 处理联系人 → stdout JSON 逐行
  │
  ▼
[Rust] BufReader 逐行读取 → emit("script-event", line)
  │
  ▼
[前端] listen("script-event") → 解析 JSON → 更新日志/计数器
  │ (对每个 success 事件)
  ▼
[前端] POST /tasks/{id}/results → 服务端幂等扣次
```

### 通信协议

桌面端 → 自动化程序（stdin）：
```json
{"run_id": "1", "daily_limit": 20, "create_tag": true, "greeting_text": "你好", "contacts": [...]}
```

自动化程序 → 桌面端（stdout 逐行）：
```json
{"run_id": "1", "contact_id": 1001, "event": "success", "message": "添加成功", "timestamp": "..."}
```

仅 `event = success` 扣试用次数。

---

## Git 提交历史

```
xxxxxxxx (HEAD -> master) feat: complete stage 3 — task panel, script integration, payment UI redesign
0bd937c docs: rewrite snapshot with comprehensive project status
cdc9d70 docs: translate snapshot to Chinese
49ca6ae docs: add project snapshot for session handoff
a14d772 chore: add desktop boilerplate files (gitignore, readme, lockfile, assets)
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

*本文档随着项目推进持续更新。每个阶段完成后更新一次。*
