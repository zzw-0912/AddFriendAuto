# FriendAuto 项目管理文档

更新时间：2026-06-29

> 本文档记录工程管理口径。当前事实以 `PROJECT_CURRENT_STATE.md` 为准。

## 1. 当前阶段

当前处于“上线前工程化与稳定性”阶段。核心功能已经具备，后续重点是支付正式化、迁移体系、打包发布、安全合规和联调稳定性。

## 2. 当前管理口径

| 主题 | 口径 |
|---|---|
| 文档事实源 | `PROJECT_CURRENT_STATE.md` |
| 新会话入口 | `SESSION_STATE.md` |
| 当前摘要 | `PROJECT_SUMMARY.md` |
| 历史规划 | `PROJECT_PLAN.md` |
| 历史快照 | `PROJECT_SNAPSHOT.md`、`SESSION_SUMMARY.md` |
| 当前支付 | 人工充值 + 后台确认收款 |
| 未来支付 | 微信支付和支付宝支付计划接入 |
| 检查入口 | `scripts/check_all.ps1` |

## 3. 关键决策

- 代码实现是唯一事实源；文档冲突时改文档，不反向改功能。
- 登录为邮箱 + 密码；注册和找回密码通过验证码。
- 服务端是会员、试用、设备、订单、任务结果的唯一可信来源。
- 当前人工充值流程不等同于官方支付。
- mock 支付 callback 只服务 debug。
- 未来官方支付必须包含验签、回调幂等、订单状态同步和后台审计。
- Alembic 迁移需要补齐，不能长期依赖 `seed.py` 补结构。

## 4. 已完成模块

- 桌面端：主界面、登录/注册/找回、任务卡片、用户教程、客服、反馈、个人中心、多账号切换。
- 后端：账号、设备、套餐、订单、会员、试用、任务、联系人、反馈、管理员和审计。
- 管理后台：用户、设备、套餐、订单、人工确认收款、任务日志、反馈、审计。
- Worker：`scripts/platform_worker.py` 真实桥接 AutoDoor。
- 网络处理：离线横幅、API 网络异常封装、任务启动离线阻断。

## 5. 后续任务

高优先级：

1. 真实 AutoDoor 联调 `daily_limit=1/2`。
2. 官方微信/支付宝支付接入方案和实现。
3. Alembic 迁移补齐，准备 PostgreSQL/RDS。
4. Windows 打包和干净机器验证。

中优先级：

1. 自动更新。
2. HTTPS 部署。
3. 接口限流。
4. 日志导出。
5. 监控告警。
6. 用户协议、隐私政策和数据删除机制。

低优先级：

1. 清理 legacy `SettingsPage.tsx`。
2. 多账号 token 迁到 Tauri 原生存储。
3. Worker 行为树 patch 测试。

## 6. 工程检查

```powershell
cd D:\FriendAuto
.\scripts\check_all.ps1
```
