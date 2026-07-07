# FriendAuto 前后端闭环测试流程

更新时间：2026-07-02
适用仓库：`D:\FriendAuto`

这份流程用于验证当前系统是否形成完整闭环：后端 API 正常、桌面端能完成用户侧动作、管理后台能承接运营动作、关键数据能回流并影响下一步业务状态。

## 1. 测试目标

主链路必须跑通：

`启动服务 -> 用户登录/注册 -> 获取权益 -> 创建订单 -> 后台确认支付 -> 权益生效 -> 启动任务 -> 领取目标 -> 回写结果 -> 扣减试用或保持会员权益 -> 任务结束 -> 后台可查 -> 用户反馈可回流`

同时验证异常链路：

- 未登录不能访问受保护接口。
- 试用次数不足时不能启动任务，并能引导充值。
- 后台确认支付只对 `pending` 订单生效，重复确认不重复开通。
- 同一个任务目标重复上报结果不会重复扣次数。
- 任务结束后未完成目标会释放回目标池。
- 后台关键操作能进入审计日志。

## 2. 测试环境准备

### 2.1 启动后端

```powershell
cd D:\FriendAuto\server
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

或：

```powershell
cd D:\FriendAuto
.\start_server.bat
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

预期：

```json
{"status":"ok","app":"FriendAuto"}
```

### 2.2 启动管理后台

```powershell
cd D:\FriendAuto\admin
npm install
npm run dev
```

访问：

```text
http://localhost:5174
```

后台默认账号：

```text
admin / admin123
```

### 2.3 启动桌面端

```powershell
cd D:\FriendAuto\desktop
npm install
npm run tauri dev
```

开发环境默认 API：

```text
http://127.0.0.1:8001
```

可用测试账号：

```text
test@friendauto.com / 888888
```

说明：该账号在 `DEBUG=true` 下有开发模式登录逻辑，适合快速跑通闭环。

## 3. 后端接口冒烟测试

接口冒烟用于快速判断后端链路是否正常，不依赖 UI。

### 3.1 用户登录并获取 token

```powershell
$Api = "http://127.0.0.1:8001"
$login = Invoke-RestMethod "$Api/auth/login" `
  -Method Post `
  -ContentType "application/json" `
  -Body (@{
    email = "test@friendauto.com"
    password = "888888"
    machine_code = "dev-machine-001"
  } | ConvertTo-Json)

$Token = $login.access_token
$Headers = @{ Authorization = "Bearer $Token" }
$login
```

预期：

- 返回 `access_token`。
- `token_type` 为 `bearer`。

### 3.2 查询用户状态

```powershell
Invoke-RestMethod "$Api/me/status" -Headers $Headers
```

预期：

- 返回 `user_id`、`email`。
- 返回 `membership`。
- 返回 `trial.total / used / remaining`，新用户通常为 20 次试用。

### 3.3 查询套餐并创建订单

```powershell
$plans = Invoke-RestMethod "$Api/plans" -Headers $Headers
$plans

$order = Invoke-RestMethod "$Api/orders" `
  -Method Post `
  -Headers $Headers `
  -ContentType "application/json" `
  -Body (@{
    plan_id = $plans[0].id
    payment_channel = "manual_wechat"
  } | ConvertTo-Json)

$order
```

预期：

- 套餐列表有月卡、季卡、年卡。
- 订单状态为 `pending`。
- 订单包含 `order_no`、`amount_cents`、`plan_id`。

### 3.4 管理员登录并确认支付

```powershell
$adminLogin = Invoke-RestMethod "$Api/admin/login" `
  -Method Post `
  -ContentType "application/json" `
  -Body (@{
    username = "admin"
    password = "admin123"
  } | ConvertTo-Json)

$AdminHeaders = @{ Authorization = "Bearer $($adminLogin.access_token)" }

Invoke-RestMethod "$Api/admin/orders/$($order.id)/confirm-payment" `
  -Method Post `
  -Headers $AdminHeaders `
  -ContentType "application/json" `
  -Body (@{
    channel = "manual_wechat"
    remark = "闭环测试确认收款"
  } | ConvertTo-Json)
```

预期：

- 返回 `success = true`。
- 再查用户状态时，`membership.is_active = true`。
- 后台订单列表中该订单为 `paid`。
- 审计日志出现确认支付记录。

### 3.5 启动任务并领取目标

```powershell
$taskCheck = Invoke-RestMethod "$Api/tasks/start-check" `
  -Method Post `
  -Headers $Headers `
  -ContentType "application/json" `
  -Body (@{
    slot_id = 1
    target_type = "phone"
    daily_limit = 2
    create_tag = $false
    greeting_text = "测试打招呼"
  } | ConvertTo-Json)

$taskCheck
```

预期：

- 权益足够时返回 `can_start = true` 和 `task_id`。
- 权益不足时返回 `can_start = false` 和原因。

领取目标：

```powershell
$targets = Invoke-RestMethod "$Api/tasks/$($taskCheck.task_id)/claim-targets" `
  -Method Post `
  -Headers $Headers

$targets
```

预期：

- 如果目标池有数据，返回 `targets`。
- 如果目标池为空，返回空列表，桌面端应结束任务并提示暂无可执行数据。

### 3.6 回写结果并结束任务

如果上一步有目标：

```powershell
$targetId = $targets.targets[0].target_id

Invoke-RestMethod "$Api/tasks/$($taskCheck.task_id)/results" `
  -Method Post `
  -Headers $Headers `
  -ContentType "application/json" `
  -Body (@{
    target_id = $targetId
    event = "success"
    message = "接口闭环测试成功"
  } | ConvertTo-Json)
```

结束任务：

```powershell
Invoke-RestMethod "$Api/tasks/$($taskCheck.task_id)/finish" `
  -Method Post `
  -Headers $Headers
```

预期：

- `success` 结果写入 `task_results`。
- 非会员用户成功结果会扣减试用次数。
- 会员用户成功结果不扣减试用次数。
- 任务状态变为 `finished`。
- 后台任务日志能看到任务和结果。

## 4. 桌面端手动测试流程

### 4.1 登录/注册流程

测试步骤：

1. 打开桌面端。
2. 用 `test@friendauto.com / 888888` 登录。
3. 确认登录后进入主页。
4. 切换到“我的”或个人信息页，查看邮箱、会员、试用次数、设备信息。
5. 使用一个新邮箱走注册流程：发送验证码、填写验证码、设置密码、自动登录。
6. 使用同一个新邮箱走找回密码流程：发送验证码、重置密码、用新密码登录。

通过标准：

- 登录成功后本地保存 token。
- `/me/status` 正常返回权益。
- 注册后后端创建用户、试用额度和设备绑定。
- 找回密码后旧密码失效，新密码可登录。
- 后台用户列表能看到新用户。

### 4.2 权益展示和充值入口

测试步骤：

1. 登录非会员账号。
2. 查看剩余试用次数。
3. 点击充值或升级会员入口。
4. 确认套餐列表来自后端 `/plans`。
5. 选择套餐并创建订单。
6. 确认弹出人工微信支付二维码和订单信息。

通过标准：

- 套餐名称、价格、有效期与后台套餐一致。
- 创建订单后后端订单为 `pending`。
- 管理后台订单页能看到该订单。
- 订单号、金额、用户邮箱在桌面端和后台一致。

### 4.3 后台确认支付后桌面端刷新

测试步骤：

1. 在管理后台登录 `admin / admin123`。
2. 进入订单管理。
3. 找到刚创建的 `pending` 订单。
4. 点击确认收款。
5. 回到桌面端刷新状态或重新进入首页。

通过标准：

- 后台订单变为 `paid`。
- 用户会员变为有效。
- 桌面端显示会员有效期。
- 季卡允许 2 个任务槽，年卡允许 3 个任务槽，月卡或非会员只允许 1 个任务槽。
- 后台审计日志出现确认支付记录。

### 4.4 任务启动前校验

测试步骤：

1. 确认桌面端已登录。
2. 进入任务配置。
3. 设置每日限额、目标类型、打招呼语。
4. 未绑定微信窗口时点击开始任务。
5. 绑定微信窗口后再次点击开始任务。
6. 断网或停后端后尝试开始任务。

通过标准：

- 未绑定微信窗口时不能启动，并提示先绑定。
- 后端不可用时不能启动，并有明确错误提示。
- 权益不足时弹出充值入口。
- 权益足够时调用 `/tasks/start-check` 并创建 `running` 任务。
- 同一用户同一槽位再次启动时，旧 `running` 任务会被收尾。

### 4.5 任务执行和结果回写

测试步骤：

1. 成功启动任务。
2. 桌面端调用 `/tasks/{task_id}/claim-targets` 领取目标。
3. 确认有目标时启动本地 worker。
4. 观察任务日志：started、progress、success、failed、invalid、finished、exited。
5. 对每个 success/failed/invalid 事件确认桌面端调用 `/tasks/{task_id}/results`。
6. 任务完成后确认调用 `/tasks/{task_id}/finish`。

通过标准：

- 每个目标最多生成一条结果。
- `success` 目标状态变为 `success`。
- `invalid` 目标状态变为 `invalid`。
- 其他失败类结果目标状态变为 `failed`。
- 重复事件不会重复扣减试用。
- 非会员只在 `success` 时扣试用次数。
- 会员不会扣试用次数。
- 后台任务页能查看任务和结果。

### 4.6 用户反馈回流

测试步骤：

1. 桌面端打开反馈入口。
2. 填写文字内容。
3. 选择 0 到多张图片上传。
4. 提交反馈。
5. 管理后台进入用户反馈页查看。

通过标准：

- 后端返回反馈 id。
- 图片保存到 `server/uploads/feedback/...`。
- 管理后台能看到反馈文字、用户邮箱和图片。
- 图片链接能正常打开。

## 5. 管理后台测试流程

### 5.1 登录和基础页面

测试步骤：

1. 打开 `http://localhost:5174`。
2. 使用 `admin / admin123` 登录。
3. 依次进入概览、用户、设备、套餐、订单、任务、审计、反馈。

通过标准：

- 登录成功后保存后台 token。
- 401 时能清除 token 并回到登录态。
- 所有列表页不报错。
- 分页、筛选、空状态显示正常。

### 5.2 用户管理

测试步骤：

1. 进入用户管理。
2. 查看用户列表。
3. 打开用户详情。
4. 修改会员：延长、冻结、解冻、过期。
5. 修改试用次数：扣减、设置剩余、清空。

通过标准：

- 用户详情展示设备、会员、试用额度。
- 会员变更后 `/me/status` 同步变化。
- 试用额度变更后桌面端同步变化。
- 每个关键操作写入审计日志。

### 5.3 设备管理

测试步骤：

1. 查看设备列表。
2. 修改设备状态为 active/inactive/blocked。
3. 添加或修改备注。
4. 测试解绑。
5. 测试重新绑定到另一个用户。

通过标准：

- 被 blocked 或解绑后的设备无法继续作为正常 active 设备使用。
- 用户详情里的设备状态同步变化。
- 审计日志记录设备操作。

### 5.4 套餐管理

测试步骤：

1. 查看默认套餐。
2. 修改名称、时长、价格、启用状态。
3. 回到桌面端打开充值弹窗。

通过标准：

- 桌面端套餐列表与后台修改一致。
- 被禁用套餐不能创建订单。
- 修改套餐写入审计日志。

### 5.5 订单管理

测试步骤：

1. 查看全部订单。
2. 按状态筛选。
3. 对 `pending` 订单确认支付。
4. 重复确认同一订单。

通过标准：

- `pending -> paid` 成功。
- 会员记录被创建或续期。
- 重复确认不会重复开通会员。
- 非 `pending` 状态订单不能被错误处理。

### 5.6 任务和审计

测试步骤：

1. 进入任务日志。
2. 查看任务列表。
3. 打开任务结果。
4. 进入操作审计。

通过标准：

- 任务状态、开始时间、结束时间、成功/失败/无效数准确。
- 结果列表能展示 event、message、是否扣试用。
- 后台支付、会员、设备、套餐操作可在审计中追溯。

## 6. 异常和边界测试清单

| 编号 | 场景 | 操作 | 预期 |
| --- | --- | --- | --- |
| E01 | 未登录访问用户接口 | 不带 token 请求 `/me/status` | 返回 401 |
| E02 | 错误密码登录 | 输入错误密码 | 返回错误提示，不发 token |
| E03 | 验证码频控 | 60 秒内重复发送验证码 | 返回 429 |
| E04 | 注册重复邮箱 | 用已注册邮箱注册 | 返回邮箱已存在 |
| E05 | 设备绑定冲突 | 同一账号换 machine_code 登录 | 返回设备绑定冲突 |
| E06 | 禁用套餐下单 | 后台禁用套餐后创建订单 | 返回套餐不存在或已禁用 |
| E07 | 重复确认支付 | 同一订单连续确认 | 不重复创建权益 |
| E08 | 试用不足启动任务 | 清空试用且无会员后启动 | 返回不能启动并引导充值 |
| E09 | 超槽位启动 | 月卡或非会员启动 slot 2/3 | 返回槽位不足 |
| E10 | 目标池为空 | 启动任务后领取目标为空 | 任务被结束，前端提示无可执行数据 |
| E11 | 重复上报结果 | 同一 target_id 连续上报 success | 第二次返回 duplicate，不重复扣次数 |
| E12 | 任务中断 | 领取目标后直接 finish | 未完成目标释放回 pending |
| E13 | 反馈无图片 | 只提交文字反馈 | 后台可查看 |
| E14 | 反馈多图片 | 提交多张图片 | 图片可访问，后台可预览 |
| E15 | 后台 token 过期 | 删除或伪造 token 后请求 | 回到登录态 |

## 7. 构建和发布前检查

发布前执行：

```powershell
cd D:\FriendAuto
powershell -ExecutionPolicy Bypass -File scripts\check_all.ps1
```

等价手动命令：

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

通过标准：

- 后端 Python 编译通过。
- worker 语法检查通过。
- 桌面端构建通过。
- 桌面端 lint 通过。
- 后台构建通过。

## 8. 闭环通过标准

本轮测试可以判定为闭环通过，需要同时满足：

- 用户能完成登录或注册。
- 用户状态能正确返回会员和试用额度。
- 用户能创建订单。
- 管理后台能确认订单收款。
- 订单确认后会员权益立即生效。
- 会员权益能影响任务槽位数量。
- 权益不足时任务不能启动，并能进入充值路径。
- 权益足够时任务能创建、领取目标、上报结果、结束。
- 任务结果能在后台查看。
- 试用扣减规则正确：非会员只扣 success，会员不扣。
- 反馈能从桌面端提交到后台。
- 后台关键操作有审计日志。
- 构建检查通过。

## 9. 建议记录模板

每轮测试建议记录：

```text
测试日期：
测试人：
代码分支/提交：
后端地址：
桌面端版本：
后台地址：
数据库：

登录/注册：通过/失败，备注：
权益状态：通过/失败，备注：
订单创建：通过/失败，备注：
后台确认支付：通过/失败，备注：
会员生效：通过/失败，备注：
任务启动：通过/失败，备注：
目标领取：通过/失败，备注：
结果回写：通过/失败，备注：
试用扣减：通过/失败，备注：
任务结束：通过/失败，备注：
反馈回流：通过/失败，备注：
后台审计：通过/失败，备注：
构建检查：通过/失败，备注：

阻塞问题：
遗留风险：
是否可发布：
```
