# FriendAuto 项目总结

生成时间：2026-06-29  
远程仓库：`git@github.com:zzw-0912/AddFriendAuto.git`  
项目目录：`D:\FriendAuto`

> 本总结描述当前功能，不再复述旧规划。若与旧 Markdown 冲突，以当前代码和 `PROJECT_CURRENT_STATE.md` 为准。

## 1. 当前产品能力

FriendAuto 当前包含：

- Windows 桌面端：登录、注册、找回密码、设备绑定、会员/试用状态、任务配置、AutoDoor worker 启停、日志展示、反馈、个人中心、多账号切换。
- FastAPI 后端：账号、设备、套餐、订单、会员、试用、任务结果、联系人、反馈、管理员和审计。
- React 管理后台：用户、设备、套餐、订单、人工确认收款、任务日志、反馈、审计日志。
- Python worker：桥接 AutoDoor 行为树项目，输出 FriendAuto JSON 事件。

## 2. 关键决策

| 主题 | 当前结论 |
|---|---|
| 登录 | 邮箱 + 密码；注册和找回密码使用 6 位验证码 |
| 设备 | 一台设备可绑定多个账号；一个账号只能绑定一台设备 |
| 试用 | 新用户 20 次成功加好友额度，仅 `success` 扣次 |
| 会员 | 会员有效期内不扣试用；续费叠加 |
| 套餐 | 月卡/季卡/年卡，价格由后端和后台配置 |
| 任务卡 | 无会员/月卡 1 张，季卡 2 张，年卡 3 张 |
| 支付现状 | 人工充值，后台确认收款后开通会员 |
| 未来支付 | 微信支付、支付宝支付为后续高概率接入方向 |
| 支付 mock | debug 用，不是正式支付能力 |
| 侧边栏 | 顶部：首页、用户教程；底部：客服、反馈、我的 |
| 设置页 | `SettingsPage.tsx` 为 legacy，不在导航 |
| 数据库 | 当前 13 张表，包含 `feedbacks` |
| 网络 | 已有离线横幅、网络异常封装和任务启动离线阻断 |

## 3. 支付说明

当前人工充值：

1. 桌面端在 `PaymentModal` 创建 `manual_wechat` 订单。
2. `QRCodeModal` 展示客服二维码和订单信息。
3. 后台订单页人工确认收款。
4. 后端共享落账逻辑创建或延长会员。

后续官方支付规划：

- 微信支付：接入商户号、回调验签、幂等、订单同步、审计。
- 支付宝支付：接入应用、回调验签、幂等、订单同步、审计。
- 保留现有人工充值作为兜底或运营通道。

## 4. 项目结构

```text
D:\FriendAuto/
├── desktop/                    # Tauri 桌面端
│   ├── src/                    # React + TypeScript UI
│   └── src-tauri/              # Rust 命令层
├── server/                     # FastAPI 后端
│   └── app/                    # api / services / schemas / models / core
├── admin/                      # React 管理后台
├── scripts/
│   ├── platform_worker.py      # 真实 AutoDoor bridge worker
│   └── check_all.ps1           # 本地检查入口
├── PROJECT_CURRENT_STATE.md    # 当前事实源
├── SESSION_STATE.md            # 新会话交接入口
└── PROJECT_SUMMARY.md          # 当前总结
```

## 5. 当前 API 能力概览

| 分类 | 已有能力 |
|---|---|
| Auth | send-code、login、register、reset-password、refresh |
| Device | bind、current |
| Profile | profile、status |
| Plans/Orders | plans、orders、order detail |
| Payments | debug mock callback |
| Tasks | start-check、results、finish |
| Contacts | search |
| Feedback | 用户反馈提交和后台查看 |
| Admin | login、users、devices、plans、orders、confirm-payment、tasks、audit、contacts、feedback |

## 6. 后续路线

高优先级：

- 用真实 AutoDoor 场景继续验证 `daily_limit=1/2` 的窗口绑定、点击位置、成功数和 UI 统计。
- 将官方微信/支付宝支付作为后续接入路线推进，补验签、回调、幂等、状态同步和审计。
- 补齐 Alembic 迁移，减少依赖 `seed.py` 补结构。

中优先级：

- 打包、自动更新、代码签名、干净 Windows 安装验证。
- 日志导出、异常告警、服务器监控。
- 评估删除 legacy `SettingsPage.tsx`。
- 评估多账号 token 从 localStorage 迁入 Tauri 原生存储。

## 7. 检查入口

```powershell
cd D:\FriendAuto
.\scripts\check_all.ps1
```
