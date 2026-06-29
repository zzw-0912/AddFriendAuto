# FriendAuto 历史会话摘要

归档时间：2026-06-29  
原摘要时间：2026-06-26

> 本文件只作为历史会话记录入口，不作为当前事实源。当前功能请读 `PROJECT_CURRENT_STATE.md` 和 `SESSION_STATE.md`。

## 当前事实速记

- 当前登录：邮箱 + 密码；注册和找回密码使用 6 位验证码。
- 当前支付：人工充值，桌面端创建 `manual_wechat` 订单，后台人工确认收款。
- 未来支付：微信支付和支付宝支付大概率接入，但当前未正式接入。
- 支付 mock：只用于 debug。
- 当前侧边栏：首页、用户教程、客服、反馈、我的。
- 设置页：`SettingsPage.tsx` 是 legacy，不在导航。
- 数据库：当前 13 张表，包含 `feedbacks`。
- 网络：已有离线横幅、网络异常封装和任务启动离线阻断。

## 推荐阅读

1. `PROJECT_CURRENT_STATE.md`
2. `SESSION_STATE.md`
3. `PROJECT_SUMMARY.md`

## 检查入口

```powershell
cd D:\FriendAuto
.\scripts\check_all.ps1
```
