# FriendAuto 新会话交接

更新时间：2026-06-29  
当前 HEAD：`ebb7322`  
当前分支：`master`  
远程仓库：`git@github.com:zzw-0912/AddFriendAuto.git`

> 下次新会话优先读本文件和 `PROJECT_CURRENT_STATE.md`。旧快照或旧规划与当前实现冲突时，以当前实现为准。

## 1. 当前功能事实

- FriendAuto 是 Windows 桌面端 + FastAPI 后端 + React 管理后台 + Python AutoDoor worker 的 monorepo。
- 登录是邮箱 + 密码；注册和找回密码使用 6 位验证码。
- debug 测试账号：`test@friendauto.com / 888888`。
- 管理员账号：`admin / admin123`。
- 一台设备可绑定多个账号；一个账号只能绑定一台设备。
- 当前支付为人工充值，桌面端创建 `manual_wechat` 订单，后台确认收款后开通会员。
- 微信支付和支付宝支付大概率后续接入，但当前不是正式能力。
- mock 支付 callback 只用于 debug，非 debug 环境禁用。
- 当前侧边栏顶部为 `首页`、`用户教程`，底部为 `客服`、`反馈`、`我的`。
- `SettingsPage.tsx` 保留为 legacy，但不在导航；设置能力已合并到 Profile。
- 当前数据库模型为 13 张表，包含 `feedbacks`。
- 网络断开处理已存在：离线横幅、API 网络异常封装、任务启动离线阻断。

## 2. 支付流程

当前人工充值流程：

1. 用户在 `desktop/src/PaymentModal.tsx` 选择套餐。
2. 桌面端调用 `POST /orders` 创建 `manual_wechat` 的 `pending` 订单。
3. 弹出 `QRCodeModal`，展示客服二维码、订单号、套餐、金额和账号。
4. 管理员在后台订单页确认收款。
5. `POST /admin/orders/{order_id}/confirm-payment` 调用共享落账逻辑，创建或延长会员。

后续官方支付路线：

- 微信支付：验签、回调、幂等、订单状态同步、后台审计。
- 支付宝支付：验签、回调、幂等、订单状态同步、后台审计。
- 当前 `/payments/wechat/callback` 和 `/payments/alipay/callback` 只能作为 debug mock。

## 3. 主要模块

| 路径 | 说明 |
|---|---|
| `desktop/src/App.tsx` | token 恢复、登录态、多账号切换 |
| `desktop/src/MainPage.tsx` | 侧边栏、首页、教程、客服/反馈/我的入口 |
| `desktop/src/ProfilePage.tsx` | 个人中心、设备信息、密码修改、多账号切换 |
| `desktop/src/TaskPanel.tsx` | 任务配置、启动/停止、日志、结果上报 |
| `desktop/src/PaymentModal.tsx` | 人工充值订单创建 |
| `desktop/src/api.ts` | API 封装、异常类、多账号本地存储 |
| `desktop/src/SettingsPage.tsx` | legacy，不在导航 |
| `desktop/src-tauri/src/lib.rs` | Tauri 命令、token、本机配置、worker 管理 |
| `scripts/platform_worker.py` | 真实 AutoDoor bridge worker |
| `server/app/api/admin.py` | 管理后台 API |
| `server/app/services/payment_service.py` | 支付/会员落账 |
| `server/app/services/admin_service.py` | 人工确认收款、审计等后台逻辑 |
| `server/app/seed.py` | SQLite 本地补列和种子数据 |

## 4. 已知风险

- 官方支付尚未接入，当前人工充值依赖运营确认。
- Alembic 只有初始迁移，后续列和表仍有部分由 `seed.py` 兼容补齐。
- `SettingsPage.tsx` 未来可删除，但本轮不要删除。
- 多账号 token 当前存于 localStorage，后续可迁到 Tauri 原生存储。
- AutoDoor 源码和项目目录在仓库外：`D:\AddFriend\autodoor_behavior_tree`、`D:\AddFriend\Addfriend`。

## 5. 下次建议先读

1. `PROJECT_CURRENT_STATE.md`
2. `SESSION_STATE.md`
3. `desktop/src/App.tsx`
4. `desktop/src/MainPage.tsx`
5. `desktop/src/ProfilePage.tsx`
6. `desktop/src/TaskPanel.tsx`
7. `desktop/src/PaymentModal.tsx`
8. `desktop/src-tauri/src/lib.rs`
9. `scripts/platform_worker.py`
10. `server/app/services/payment_service.py`
11. `server/app/services/admin_service.py`
12. `server/app/seed.py`

## 6. 检查入口

```powershell
cd D:\FriendAuto
.\scripts\check_all.ps1
```

如果需要拆开执行：

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
