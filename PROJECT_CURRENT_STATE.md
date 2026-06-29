# FriendAuto 当前项目状态

更新时间：2026-06-29  
当前 HEAD：`ebb7322`  
远程仓库：`git@github.com:zzw-0912/AddFriendAuto.git`  
项目目录：`D:\FriendAuto`

> 本文档是当前事实源。代码实现与旧 Markdown 冲突时，以当前代码实现为准。

## 1. 项目定位

FriendAuto 是一个 Windows 桌面端自动加好友工具。桌面端负责登录、设备绑定、会员/试用状态展示、任务配置、启动本地 Python worker、展示运行结果并上报后端。后端负责账号、设备、会员、试用、订单、任务结果、反馈和管理后台数据。Python worker 负责桥接 AutoDoor 行为树项目执行本机微信自动化。

## 2. 当前已锁定事实

| 主题 | 当前实现 |
|---|---|
| 桌面端 | Tauri v2 + React + TypeScript + Vite |
| 后端 | FastAPI + SQLAlchemy，开发 SQLite，生产目标为 PostgreSQL / RDS |
| 登录 | 邮箱 + 密码登录；注册和找回密码使用 6 位邮箱验证码 |
| 设备绑定 | 一台设备可绑定多个账号；一个账号只能绑定一台设备 |
| 多账号切换 | `localStorage` 键 `friendauto.accounts` 保存最多 5 个账号 token |
| 支付现状 | 人工充值：桌面端创建 `manual_wechat` 订单，后台人工确认收款后开通会员 |
| 未来支付 | 大概率接入微信支付和支付宝支付；当前只作为待实现路线 |
| 支付 mock | `/payments/wechat/callback` 和 `/payments/alipay/callback` 仅用于 debug，不是正式支付能力 |
| 任务卡片 | 无会员/月卡 1 张，季卡 2 张，年卡 3 张 |
| 侧边栏 | 顶部：首页、用户教程；底部：客服、反馈、我的 |
| 设置页 | `SettingsPage.tsx` 保留为 legacy，但当前不在导航；功能已合并到 Profile |
| 网络处理 | 已有 `OfflineBanner`、`useNetworkStatus`、API 网络异常封装和任务启动离线阻断 |
| 数据库模型 | 当前 13 张表，包含 `feedbacks` |

## 3. 当前支付口径

当前线上/开发主流程是人工充值：

1. 用户在 `PaymentModal` 选择套餐。
2. 桌面端调用 `POST /orders` 创建 `manual_wechat` 的 `pending` 订单。
3. `QRCodeModal` 展示客服/微信二维码、订单号、套餐、金额和登录账号。
4. 管理员在后台订单页执行 `POST /admin/orders/{order_id}/confirm-payment`。
5. 后端统一走订单落账逻辑，创建或延长会员。

未来微信支付和支付宝支付接入时，需要补齐验签、回调、幂等、订单状态同步和后台审计。现有 mock callback 只能用于 debug 验证，不应写成正式能力。

## 4. 已完成能力

- 桌面端主流程：登录、注册、找回密码、token 恢复、侧边栏导航、首页轮播、用户教程、客服二维码、反馈弹窗、个人中心、多账号切换。
- 任务流程：任务前校验、按套餐渲染任务卡、启动/停止 worker、终端式 boot 动画、实时事件日志、结果去重、结果上报。
- 后端业务：用户、设备、套餐、订单、会员、试用、任务、联系人、反馈、管理员鉴权、审计日志。
- 管理后台：用户管理、设备管理、套餐管理、订单管理、人工确认收款、任务日志、审计日志、反馈查看和图片预览。
- AutoDoor 桥接：`scripts/platform_worker.py` 读取配置，复制运行副本，补丁行为树，处理 DPI 和窗口绑定，并输出 FriendAuto JSON 事件。

## 5. 架构边界

| 模块 | 负责 | 不负责 |
|---|---|---|
| 桌面端 | UI、登录态、任务配置、调用后端、启动 worker、展示日志 | 裁决会员/试用/支付 |
| Tauri Rust 层 | 本机命令、token 落盘、AutoDoor 配置、worker 进程管理 | 业务规则判断 |
| 后端 | 账号、设备、会员、试用、订单、任务结果、反馈、审计 | 直接控制微信窗口 |
| Python worker | AutoDoor 运行副本、行为树补丁、自动化执行、事件输出 | 商业规则判断 |
| AutoDoor 项目 | GUI 自动化动作 | FriendAuto 业务模型 |

## 6. 重要文件

| 文件 | 作用 |
|---|---|
| `desktop/src/App.tsx` | 应用入口、token 恢复、多账号切换 |
| `desktop/src/MainPage.tsx` | 主界面、侧边栏、首页、教程、弹窗入口 |
| `desktop/src/ProfilePage.tsx` | 我的页面、设备/账号信息、密码修改、多账号切换 |
| `desktop/src/TaskPanel.tsx` | 任务配置、启动/停止、日志、结果上报 |
| `desktop/src/PaymentModal.tsx` | 人工充值入口，创建 `manual_wechat` 订单 |
| `desktop/src/QRCodeModal.tsx` | 客服二维码和订单信息展示 |
| `desktop/src/api.ts` | API 工具、错误封装、多账号本地存储 |
| `desktop/src/SettingsPage.tsx` | legacy，不在导航 |
| `desktop/src-tauri/src/lib.rs` | Tauri 命令、token、AutoDoor 配置、worker 管理 |
| `scripts/platform_worker.py` | 真实 AutoDoor 桥接 worker |
| `server/app/services/payment_service.py` | 订单支付落账共享逻辑 |
| `server/app/services/admin_service.py` | 管理后台业务，含人工确认收款 |
| `server/app/api/payments.py` | debug mock 支付回调 |
| `server/app/seed.py` | 本地初始化、SQLite 兼容补列、种子数据 |

## 7. 当前风险和后续路线

- 官方微信/支付宝支付尚未接入，但已作为高概率后续路线保留。
- Alembic 迁移需要补齐新表和新列，逐步减少依赖 `seed.py` 补结构。
- `SettingsPage.tsx` 未来可单独评估删除，当前不删除。
- 多账号 token 当前保存在 localStorage，后续可迁到 Tauri 原生存储。
- 需要继续推进打包、自动更新、代码签名、安装验证、协议和隐私政策。

## 8. 推荐检查命令

可直接运行：

```powershell
.\scripts\check_all.ps1
```

等价检查项：

```powershell
cd D:\FriendAuto\server
python -m compileall app

cd D:\FriendAuto
python -m py_compile scripts\platform_worker.py

cd D:\FriendAuto\desktop
npm run build
npm run lint

cd D:\FriendAuto\admin
npm run build
```
