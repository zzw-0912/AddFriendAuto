# FriendAuto — 项目快照

## Git
- 远程仓库: `https://github.com/zzw-0912/AddFriendAuto.git`
- 分支: `master` — 所有提交已推送

## 架构
- **desktop/** — Tauri v2 + React + TypeScript + Vite
- **server/** — FastAPI + SQLAlchemy（开发 SQLite / 生产 PostgreSQL）
- **scripts/** — Python 自动化脚本

## 启动命令
| 组件 | 命令 |
|------|------|
| 后端 | `cd server; $env:PYTHONPATH="$pwd"; uvicorn app.main:app --reload --port 8001` |
| 桌面端 | `cd desktop; npm run tauri dev` |
| 重置数据库 | 删除 `server/friendauto.db` |
| 杀掉端口 | `Stop-Process -Id (netstat -ano \| findstr ':8001' \| Select-Object -First 1) -replace '.*\s+(\d+)$','$1' -Force` |

## 测试账号
- `test@friendauto.com` / 验证码 `888888` — 跳过设备绑定，无需 SMTP

## API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/auth/send-code` | 发送验证码 |
| POST | `/auth/login` | 登录/注册 + 设备绑定 |
| POST | `/auth/refresh` | 刷新 Token |
| POST | `/devices/bind` | 绑定设备 |
| GET | `/devices/current` | 当前设备信息 |
| GET | `/me/status` | 会员 + 试用状态 |
| GET | `/plans` | 套餐列表 |
| POST | `/orders` | 创建订单 |
| GET | `/orders/{id}` | 查询订单 |
| POST | `/payments/wechat/callback` | 模拟微信支付回调 |
| POST | `/payments/alipay/callback` | 模拟支付宝支付回调 |

## 数据库表（12 张）
`users`, `verification_codes`, `devices`, `memberships`, `plans`, `orders`,
`payments`, `email_configs`, `trial_quotas`, `friend_tasks`, `task_results`,
`task_logs`

## 套餐数据
| 名称 | 价格 | 时长 |
|------|------|------|
| 月度会员 | ¥29.9 | 30 天 |
| 季度会员 | ¥79.9 | 90 天 |
| 年度会员 | ¥299.9 | 365 天 |

## 业务规则
- 新用户自动获得 20 次试用额度
- 登录时自动绑定设备；第二个设备返回 403
- 测试账号 `test@friendauto.com` 跳过设备绑定
- 会员续费：新周期在当前有效周期结束后开始（叠加）
- 支付回调：开发环境通过 `POST /payments/wechat/callback?order_no=...` 模拟

## 关键文件
- `server/app/main.py` — 应用入口，注册所有路由
- `server/app/services/auth_service.py` — 认证逻辑（发送验证码、登录、试用额度、设备绑定）
- `server/app/services/payment_service.py` — 支付模拟 + 会员激活
- `server/app/services/status_service.py` — 用户状态（会员 + 试用）
- `desktop/src/LoginPage.tsx` — 三标签登录界面
- `desktop/src/MainPage.tsx` — 主界面含状态栏
- `desktop/src/PaymentModal.tsx` — 套餐选择 + 支付弹窗
- `desktop/src-tauri/src/lib.rs` — Rust 命令（机器码、Token、脚本执行）

## 下一阶段（Stage 3）
任务管理：`POST /tasks/start-check`、`POST /tasks/{id}/results`、实时日志、脚本集成。
