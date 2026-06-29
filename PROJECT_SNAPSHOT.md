# FriendAuto 历史快照

归档时间：2026-06-29  
原快照时间：2026-06-26

> 本文件是历史快照入口，不作为当前事实源。当前状态请读 `PROJECT_CURRENT_STATE.md`，新会话交接请读 `SESSION_STATE.md`。

## 1. 为什么归档

该文件最初用于记录 2026-06-26 前后的项目状态。随后项目继续演进，登录、支付、侧边栏、设置页、反馈、网络处理和 AutoDoor worker 都发生了变化。为避免旧结论误导后续开发，本文件只保留归档说明。

## 2. 当前事实源

- 当前状态：`PROJECT_CURRENT_STATE.md`
- 新会话交接：`SESSION_STATE.md`
- 当前摘要：`PROJECT_SUMMARY.md`
- 历史规划：`PROJECT_PLAN.md`

## 3. 需要特别注意的变化

- 当前登录是邮箱 + 密码；注册和找回密码使用 6 位验证码。
- 当前支付是人工充值；微信支付和支付宝支付是后续高概率路线，尚未正式接入。
- debug mock 支付 callback 不是正式支付能力。
- 当前侧边栏是首页/用户教程 + 客服/反馈/我的。
- `SettingsPage.tsx` 是 legacy，不在导航。
- 当前数据库模型为 13 张表，包含 `feedbacks`。
- 当前已有网络异常提示和任务启动离线阻断。

## 4. 当前检查入口

```powershell
cd D:\FriendAuto
.\scripts\check_all.ps1
```
