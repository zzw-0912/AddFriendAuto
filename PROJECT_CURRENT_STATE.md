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

### 2.3 架构边界

- 服务端是会员、试用、设备绑定、订单、支付状态的唯一可信来源
- 桌面端不保存支付密钥，不做会员或试用判断
- Python 脚本只执行自动化，不感知会员和支付逻辑
- 管理后台用于用户、设备、套餐、订单、任务和审计运营

---

## 3. 已完成部分

### 3.1 桌面端

- 登录页已完成：登录 / 注册 / 找回密码三标签流程
- 主界面已完成：状态栏、会员入口、任务卡片、反馈入口、客服二维码
- 套餐卡片已按 `plan_id` 控制渲染数量
- 已完成任务面板与 Python 测试脚本联调
- 已新增“我的”页面：
  - 拉取 `/me/profile`
  - 展示账号信息、会员状态、累计成功/失败/无效数
  - 展示推荐码和二维码，支持复制推荐码
- 已新增“设置”页面：
  - 任务默认配置（每日限额 / 创建标签 / 打招呼语）
  - 本地持久化 `friendauto.taskDefaults.v1`
  - 设备信息、设备码复制、应用版本展示
  - 修改密码（复用验证码发送和重置密码接口）
  - 清除本地任务默认配置、退出登录

### 3.2 后端

- 已完成账号体系：
  - `send-code`
  - `login`
  - `register`
  - `reset-password`
  - `refresh`
- 已完成设备体系：
  - 设备绑定
  - 当前设备查询
  - 一账号一设备约束
- 已完成会员和试用体系：
  - 试用额度创建
  - 会员有效期读取
  - 订单与 mock 支付回调
- 已完成任务体系：
  - 启动前校验
  - 执行结果上报
  - 任务结束
  - 幂等扣次
- 已新增 profile 能力：
  - `/me/profile`
  - 聚合用户信息、会员/试用状态、任务结果统计、推荐码

### 3.3 管理后台

- 管理员登录
- 用户列表 / 用户详情
- 会员操作
- 设备列表 / 解绑 / 改绑 / 备注
- 套餐价格管理
- 订单管理
- 任务日志与执行结果查看
- 操作审计日志

---

## 4. 当前待办

### 4.1 上线前高优先级

1. 接入真实微信支付与支付宝支付，完成验签和回调幂等
2. 切换 PostgreSQL 生产数据库并验证迁移
3. 进行桌面端打包和安装链路验证
4. 增加接口限流和关键错误处理
5. 补齐部署、HTTPS、监控、异常告警

### 4.2 产品和体验待补

1. 桌面端真实联系人导入 / 筛选链路仍较弱，当前更偏脚本联调形态
2. 网络异常、服务端不可用、支付超时的用户提示还可以继续加强
3. 自动更新、日志导出、安装包签名尚未落地
4. 协议与隐私文档、正式上线法务信息未补齐

### 4.3 脚本集成待替换

- 当前 `scripts/test_autobot.py` 仍是测试脚本
- 未来需替换为真实业务自动化脚本，但保持 stdin/stdout JSON 协议不变

---

## 5. 当前架构思路

### 5.1 总体结构

```text
桌面端 (Tauri + React)
  -> REST API
后端 (FastAPI + SQLAlchemy)
  -> SQLite / PostgreSQL

桌面端
  -> Rust Command
Python 自动化脚本
```

### 5.2 数据流

```text
用户登录
  -> 桌面端获取 token 与 machineCode
  -> 保存本地 auth.json

用户启动任务
  -> 前端提交 /tasks/start-check
  -> 校验通过后 invoke("start_task")
  -> Rust 启动 Python 脚本并写入 JSON 配置
  -> Python 输出逐行 JSON 事件
  -> Rust emit("script-event")
  -> 前端更新日志与计数，并按 success 上报 /tasks/{id}/results
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

## 6. 重要文件

### 6.1 桌面端关键文件

| 文件 | 作用 |
|---|---|
| `desktop/src/App.tsx` | 应用入口，恢复 token，切换登录页和主界面 |
| `desktop/src/LoginPage.tsx` | 登录 / 注册 / 找回密码 |
| `desktop/src/MainPage.tsx` | 侧边栏、主内容切换、状态拉取、任务卡片分发 |
| `desktop/src/ProfilePage.tsx` | 用户资料页 |
| `desktop/src/SettingsPage.tsx` | 设置页 |
| `desktop/src/TaskPanel.tsx` | 单张任务卡的配置、日志、状态与脚本控制 |
| `desktop/src/useSendCode.ts` | 验证码发送和倒计时复用逻辑 |
| `desktop/src/types.ts` | 桌面端共享类型和任务默认值常量 |
| `desktop/src-tauri/src/lib.rs` | Tauri 命令、token 本地存储、脚本进程管理 |

### 6.2 后端关键文件

| 文件 | 作用 |
|---|---|
| `server/app/main.py` | FastAPI 应用入口，挂载所有路由 |
| `server/app/core/database.py` | 数据库连接和 SQLite 相对路径解析 |
| `server/app/core/security.py` | JWT、密码哈希、验证码校验 |
| `server/app/services/auth_service.py` | 登录、注册、找回密码、设备绑定、推荐码生成 |
| `server/app/services/status_service.py` | 会员与试用状态聚合 |
| `server/app/services/profile_service.py` | 个人资料统计聚合 |
| `server/app/services/payment_service.py` | 订单、支付回调、会员叠加 |
| `server/app/services/task_service.py` | 任务校验、结果上报、扣次、结束任务 |
| `server/app/seed.py` | 初始化建表、兼容补列、套餐和管理员种子 |

### 6.3 项目文档入口

| 文件 | 用途 |
|---|---|
| `PROJECT_PLAN.md` | 原始规划 |
| `PROJECT_MANAGEMENT.md` | 阶段推进记录 |
| `PROJECT_SUMMARY.md` | 早期总结 |
| `PROJECT_SNAPSHOT.md` | 跨会话交接快照 |
| `SESSION_STATE.md` | 上一次较详细会话快照 |
| `PROJECT_CURRENT_STATE.md` | 当前最新交接入口，优先阅读 |

---

## 7. 最近重要修改记录

### 7.1 已在历史提交中的关键阶段

| 提交 | 说明 |
|---|---|
| `24c92d8` | 后台管理完成 |
| `76bafed` | 密码登录、真实 SMTP、登录页重做 |
| `151d8eb` | 设备绑定调整为多账号可共设备 / 一账号一设备 |
| `9cda912` | 主界面布局重写与充值 UI 重做 |
| `45d9b05` | 主导航精简，仅保留底部导航 |
| `ab08843` | 按会员套餐层级渲染多张任务卡 |
| `b2d8848` | 反馈上传与后台预览 |

### 7.2 当前工作树新增能力（本次准备提交）

| 领域 | 关键文件 | 修改内容 |
|---|---|---|
| 个人资料接口 | `server/app/api/profile.py` `server/app/services/profile_service.py` `server/app/schemas/profile.py` | 新增 `/me/profile` 聚合接口 |
| 用户模型扩展 | `server/app/models/user.py` `server/app/seed.py` | 新增 `referral_code` 字段并对旧 SQLite 做兼容补列和补数 |
| 登录注册逻辑 | `server/app/services/auth_service.py` | 注册与测试账号创建时生成推荐码 |
| 应用路由 | `server/app/main.py` | 挂载 profile 路由 |
| 桌面端个人页 | `desktop/src/ProfilePage.tsx` | 展示账号、会员、统计、推荐码 |
| 桌面端设置页 | `desktop/src/SettingsPage.tsx` | 设置页完整落地 |
| 本地设置复用 | `desktop/src/types.ts` `desktop/src/useSendCode.ts` | 抽出共享类型和验证码 hook |
| 主界面接线 | `desktop/src/MainPage.tsx` `desktop/src/TaskCard.tsx` `desktop/src/TaskPanel.tsx` | 接入 profile / settings 和任务默认值同步 |
| 样式层 | `desktop/src/MainPage.css` | 新增 profile/settings 页面样式 |

---

## 8. 当前数据库与业务要点

- 用户表已有 `password_hash` 和 `referral_code`
- membership 已有 `plan_id`
- SQLite 初始化逻辑放在 `seed.py`，通过 `ALTER TABLE` 做兼容补列
- 推荐码会为历史缺失用户补齐
- 试用次数只在 `success` 时扣减
- 设备规则是：
  - 同一设备可供多个账号使用
  - 同一账号只能绑定一个设备

---

## 9. 启动与续接方式

### 9.1 常用启动命令

```powershell
# server
cd D:\FriendAuto\server
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# desktop
cd D:\FriendAuto\desktop
npm run tauri dev

# admin
cd D:\FriendAuto\admin
npm run dev
```

### 9.2 测试账号

- 用户测试：`test@friendauto.com`
- 测试密码 / 验证码：`888888`
- 管理员：`admin` / `admin123`

### 9.3 下次新会话建议入口

1. 先读 `PROJECT_CURRENT_STATE.md`
2. 再看 `git status` 和 `git log --oneline -n 10`
3. 若做桌面端相关功能，优先从 `desktop/src/MainPage.tsx` 和 `desktop/src-tauri/src/lib.rs` 切入
4. 若做后端业务，优先从 `server/app/main.py`、`api/`、`services/` 三层切入

---

## 10. 当前风险和注意事项

1. 真实支付还未接入，当前充值流程仍依赖 mock 回调
2. SQLite 兼容补列逻辑越来越多，后续切 PostgreSQL 时要认真梳理迁移脚本
3. 当前桌面端已经有较多状态入口，后续继续扩展时要注意不要把 `MainPage.tsx` 做得过重
4. Python 脚本仍是测试替身，真正接业务脚本时要保持 JSON 协议兼容
5. 当前 master 上存在持续演进的本地修改，提交前需要统一打包入库，避免交接断层
