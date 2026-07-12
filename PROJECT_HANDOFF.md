# FriendAuto 项目交接摘要

更新时间：2026-07-12  
当前分支：`codex/mysql-migration-support`  
远程仓库：`origin git@github.com:zzw-0912/AddFriendAuto.git`

## 1. 项目架构

- `server/`：FastAPI 后端，负责登录注册、会员/免费次数、任务领取、任务结果上报、后台接口、轮播图、强制更新配置。线上默认连接服务器数据库，客户端不直接连数据库。
- `desktop/`：Tauri + React 客户端。默认 API 地址为 `http://47.111.3.83:8001`，所有客户端请求会携带版本头并支持强制更新弹窗。
- `admin/`：React 后台管理系统。包含用户、设备、套餐、订单、任务日志、轮播图管理、版本控制、操作审计、用户反馈。
- `scripts/platform_worker.py`：客户端启动的自动化 worker，负责调 AutoDoor 流程、控制微信窗口、上报任务事件。
- `automation/autodoor_behavior_tree/`：AutoDoor 自动化平台与测试。
- 客户安装包只应给 `FriendAuto_0.1.0_x64-setup.exe`，不要把 `server/`、`admin/`、数据库、日志、上传目录、源码脚本直接给客户。

## 2. 关键产品决策

- 非会员免费次数只在 `success` 时扣减，`failed` 和 `invalid` 不扣。
- “每日限额”现在表示目标成功数，不是处理名单数。失败或无效要继续补领，直到成功数达到限额、名单耗尽、免费次数耗尽、会员月度额度触顶，或出现真实异常。
- 任务结果上报失败时必须停止整任务，不能继续补领下一批，避免次数和名单状态错乱。
- 批次之间立即补领并继续执行，不额外加一次号龄等待；批内仍按号龄随机间隔等待。
- 号龄配置：
  - 新号：每日 5 个，20 到 30 分钟随机间隔。
  - 中期号：每日 15 个，15 到 20 分钟随机间隔。
  - 老号：每日 30 个，5 到 10 分钟随机间隔。
  - 用户手动修改每日限额后，以手动输入为准。
- 会员前端展示仍是无限使用，但后端有隐藏月度成功上限：单窗口每月最多 700，双窗口最多 1400。
- 充值套餐当前只展示 300 和 500 两档，800 档先隐藏。
- 注册邀请码闭环：注册时填写有效邀请码，推荐人免费次数增加 20；不存在的邀请码阻止注册。
- 强制更新通过后台版本控制开启。后端对版本不一致客户端返回 `426 Upgrade Required`，新客户端会弹不可关闭更新弹窗。
- 后台轮播图统一管理客户端首页 3 张图；客户端进入首页或切回首页时拉取最新配置。
- 线上数据库和 `task_targets` 表不能随意清空或删除，任何数据修复前必须先备份并确认 SQL。

## 3. 已完成的重点功能

- 客户端任务提醒样式和文案已改为 AI 模型思考、搜索、整合信息，并在等待间隔期间循环追加提示。
- 加人间隔等待期间新增合法网页探测请求，访问 `zcool`、`68design`、`ui.cn`、`gtn9`，请求发生在已有等待时间内，不额外增加间隔。
- worker 增加多种异常保护：
  - 同一微信号重复输入达到阈值后终止。
  - 流程异常会停止当前任务。
  - 等待间隔期间仍可响应停止请求。
  - 已有 worker 日志写入 `friendauto_worker.txt`，客户端日志写入 `friendauto_client.txt`。
- 客户端打包已支持 `runtime.pak` 加密封装，安装目录只暴露应用和加密运行包。
- Tauri 后端支持隐藏子进程黑窗口，优先解析加密 runtime 内资源。
- 后台已具备轮播图管理和客户端版本控制入口。
- 客户端登录、注册、提示弹窗已尽量改为中文，登录注册限制 QQ 邮箱在前端校验。
- 微信绑定窗口逻辑已加入：有次数或会员有效时，开始任务前要求先绑定微信窗口。
- 充值窗口话术已调整，300/500 两档均匀展示。
- 已生成最近客户安装包：`D:\wxfriend\FriendAuto_0.1.0_x64-setup.exe`。

## 4. 本次提交包含的核心改动

- `desktop/src/TaskPanel.tsx`
  - 从一次性任务改为批次循环：`start-check` 只做一次，同一 `task_id` 下反复 `claim-targets`。
  - `finished` 只标记本批结束，`exited` 后等待全部结果上报，再决定结束或补领。
  - 结果上报失败会设置失败标记、停止 worker、结束任务，不补领下一批。
  - 清理旧的不可达代码，删除旧的一次性 `claim-targets -> start_task` 逻辑。
- `server/app/services/task_service.py`
  - 新增按任务成功数统计，`claim_targets()` 按剩余成功目标领取。
  - 已成功达到每日限额时返回 `goal_reached` 并结束任务。
  - 名单池不足时返回 `targets_exhausted`。
  - 免费次数或会员隐藏额度不足时返回明确 `reason_code`。
- `server/app/schemas/task.py`
  - `ClaimTargetsResponse` 增加 `reason_code`。
- `scripts/platform_worker.py`
  - 等待间隔改为 `wait_with_legal_probes()`，在原等待期间按间隔请求指定网站并写日志。
- `automation/autodoor_behavior_tree/tests/test_friendauto_worker_patch.py`
  - 增加等待期间网页探测不拉长等待的测试。
- `server/tests/test_task_service_claim_limits.py`
  - 增加按成功数补领、失败/无效不减少目标、成功达标停止、名单耗尽停止等测试。
- `desktop/public/qr-wechat-2.png`
  - 更新第二张微信联系人二维码图片。
- 旧的零散交接文档已移除，统一用当前 `PROJECT_HANDOFF.md` 作为新会话入口。

## 5. 验证记录

本次提交前已通过：

```powershell
D:\APP\Python3.10\python.exe -m unittest server.tests.test_task_service_claim_limits server.tests.test_task_service_report_result server.tests.test_task_service_member_monthly_limit
D:\APP\Python3.10\python.exe -m unittest automation.autodoor_behavior_tree.tests.test_friendauto_worker_patch
cd D:\FriendAuto\desktop
npm run build
```

最近一次 `npm run build` 会重新生成加密 `runtime.pak`，但没有重新执行 Tauri 安装包打包。

## 6. 部署和打包注意事项

- 更新线上服务时，至少需要部署后端 `server/`。如果后台页面改动需要生效，也要重新构建并部署 `admin/`。
- 客户端改动需要重新打 Tauri 安装包并让用户安装新包；后端强制更新弹窗只有新客户端才有完整体验。
- 客户包只给安装包，不要附带：
  - `server/`
  - `admin/`
  - `.env`
  - `friendauto.db`
  - `uploads/`
  - `logs/`
  - `.git/`
  - 测试、缓存、源码自动化脚本明文目录。
- 当前推荐客户包输出目录：`D:\wxfriend`。
- 本地 `nuitka-crash-report.xml` 是调试残留，不应提交或发给客户。

## 7. 待办事项

- 线上部署后，用真实账号验证：
  - 非会员成功才扣次数。
  - 失败/无效会自动补领。
  - 结果上报失败时停止整任务，不继续补领。
  - 会员隐藏月度额度生效但前端不展示限制。
- 用 2、5、20、30 个目标分别跑真实微信流程，重点看第二条及后续是否重新走完整加好友流程。
- 后台强制更新需要再用不同版本客户端验证 `426` 弹窗链路。
- 后台轮播图上传需在线上环境验证 `/uploads` 静态访问权限和日志。
- 每次上线前备份线上数据库，尤其不要直接改动或清空 `task_targets`。
- 如继续优化加密，优先保持 `runtime.pak` 稳定方案；Nuitka onefile 曾遇到 AutoDoor 依赖冲突，不建议作为主方案。
