# FriendAuto 项目交接快照

更新时间：2026-06-28  
项目目录：`D:\FriendAuto`  
远程仓库：`https://github.com/zzw-0912/AddFriendAuto.git`  
当前分支：`master`  
当前基线提交：`6f3bea7`

---

## 1. 项目定位与总体架构

FriendAuto 是 Windows 桌面端自动加好友工具。用户在桌面端完成登录、设备绑定、会员/试用校验和任务配置后，由本地 Python worker 调用 AutoDoor 行为树项目执行微信自动化，并把结果通过 stdout JSON 事件流返回桌面端，再由桌面端上报后端。

```text
React + Tauri 桌面端
  -> FastAPI 后端：账号、设备、会员、试用、任务、结果
  -> Rust Command 启动 Python worker
  -> Python worker 拷贝并补丁 AutoDoor 项目
  -> AutoDoor BehaviorTreeEngine 执行微信行为树
  -> stdout JSON line 事件回到桌面端
```

核心职责边界：

| 模块 | 职责 | 不负责 |
|---|---|---|
| 桌面端 | UI、登录态、机器码、任务配置、启动/停止 worker、展示日志、上报结果 | 不裁决会员/试用规则 |
| 后端 | 注册登录、设备绑定、会员状态、试用扣次、任务结果幂等 | 不执行本机自动化 |
| Python worker | 读任务 JSON、准备 AutoDoor 运行副本、执行引擎、输出事件 | 不判断商业规则 |
| AutoDoor 项目 | 图像识别、点击、输入、窗口绑定等实际自动化动作 | 不知道 FriendAuto 会员/任务模型 |

---

## 2. 关键决策

| 决策 | 当前结论 |
|---|---|
| 桌面技术栈 | Tauri v2 + React + TypeScript |
| 后端技术栈 | FastAPI + SQLAlchemy，开发用 SQLite |
| 脚本通信 | Rust `Command` 启动 Python，stdin 输入任务 JSON，stdout 逐行输出 JSON |
| 自动化接入 | 不再使用 `scripts/test_autobot.py`，改用 `scripts/platform_worker.py` 作为真实 AutoDoor 桥接 |
| AutoDoor 默认路径 | 源码：`D:\AddFriend\autodoor_behavior_tree`；项目：`D:\AddFriend\Addfriend` |
| AutoDoor 配置持久化 | `%APPDATA%\FriendAuto\autodoor.json` |
| 运行副本 | 每次任务复制 AutoDoor 项目到 `%APPDATA%\FriendAuto\runs\<run_id>\Addfriend`，只修改副本 |
| DPI | worker 必须调用 AutoDoor 的 `initialize_dpi_awareness()`，否则坐标会偏 |
| 手机号来源 | 当前仍从 AutoDoor 行为树“输入手机号”节点的 `preset_texts` 读取 |
| 扣次规则 | 只有 worker 输出 `event=success` 时，后端才扣试用次数 |
| 结果幂等 | 后端按 `task_id + contact_id` 去重，避免重复扣次 |

---

## 3. 已完成部分

后端与桌面基础：

- 邮箱密码登录、注册、找回密码、验证码、token 持久化。
- 设备绑定、会员状态、试用次数、任务创建和结果上报。
- 后台管理、反馈、订单、套餐、任务日志等基础页面。
- 桌面端主界面、设置页、任务面板、网络异常提示。

AutoDoor 集成：

- 新增真实 worker：`scripts/platform_worker.py`。
- Tauri `start_task` 已改为启动 worker，而不是测试脚本。
- worker 支持读取 `%APPDATA%\FriendAuto\autodoor.json`，默认使用 `D:\AddFriend` 下的 AutoDoor 路径。
- 设置页新增“自动化平台设置”，可保存 AutoDoor 源码目录、项目目录、编辑器 exe 路径，并可直接打开编辑器。
- worker 运行前会：
  - 拷贝 AutoDoor 项目到每次运行目录。
  - 按 `daily_limit` 截取手机号池。
  - 写入打招呼语。
  - 根据 `create_tag=false` 跳过标签/备注流。
  - 只从 root 可达且启用的“输入手机号”节点取号码，避免禁用副本干扰。
  - 校验手机号必须是 11 位数字，坏号会提前报错。
  - 调用 AutoDoor DPI 初始化，修正 FriendAuto 启动时坐标偏差。
- 前端任务收尾加了 `isFinishingRef`，避免 `finished` 和 `exited` 两个事件重复结束任务。
- Rust 启动 worker 时设置 `PYTHONIOENCODING=utf-8` 和 `PYTHONUTF8=1`，避免中文/emoji 在 Windows GBK 环境下输出失败。

本地 AutoDoor 项目状态：

- `D:\AddFriend\Addfriend\tree.json` 的 `node_45.config.preset_texts[0]` 已从 `1355906309` 修为 `13559063090`。
- 这个文件位于仓库外，不能随 FriendAuto git 提交一起推送；新机器或新 AutoDoor 项目需要单独确认。

---

## 4. 重要文件修改记录

| 文件 | 作用 | 本次关键修改 |
|---|---|---|
| `scripts/platform_worker.py` | FriendAuto 到 AutoDoor 的桥接 worker | 新增运行副本、行为树补丁、手机号校验、DPI 初始化、AutoDoor 事件转 FriendAuto 事件 |
| `desktop/src-tauri/src/lib.rs` | Tauri Rust 命令层 | 新增 AutoDoor 配置读写、打开编辑器、启动 worker、stderr 转错误事件、UTF-8 环境变量 |
| `desktop/src/SettingsPage.tsx` | 桌面端设置页 | 新增自动化平台路径配置表单和打开编辑器按钮 |
| `desktop/src/types.ts` | 前端共享类型 | 新增 `AutoDoorConfig` |
| `desktop/src/MainPage.css` | 桌面端样式 | 新增自动化路径设置输入布局 |
| `desktop/src/TaskPanel.tsx` | 任务启动与日志面板 | 传 `task_id` 给 worker，避免重复 finish，保留网络断开时阻止启动 |
| `D:\AddFriend\Addfriend\tree.json` | AutoDoor 行为树项目 | 仓库外修改：修正 `node_45` 第一条手机号为 11 位 |

---

## 5. 当前验证结果

已通过：

```powershell
python -m py_compile scripts\platform_worker.py
npm run build
cargo check
```

已做过的 worker 探针：

- `patch_tree(daily_limit=1, create_tag=true)` 能稳定取到 `13559063090`。
- `patch_tree(daily_limit=2, create_tag=false)` 能稳定取前两条号码并跳过标签/备注流。
- 连续多次补丁探针不再随机读取禁用节点。
- 坏号会提前报错，例如：`手机号池包含无效手机号: node=node_45, index=0, value='123'`。
- worker 调用 `import_autodoor()` 后，`bt_utils.dpi_awareness.get_dpi_scale()` 在当前机器上为 `1.5`，与 AutoDoor Dist 启动行为一致。

尚未完成稳定验收：

- 需要用 FriendAuto 桌面端执行一次受控真实任务（建议 `daily_limit=1`）。
- 真实跑前建议只保留一个目标微信主窗口，避免同名窗口标题导致 AutoDoor 绑定不确定。

---

## 6. 当前待办事项

高优先级：

1. 用 FriendAuto 桌面端真实启动 `daily_limit=1`，确认点击位置与 AutoDoor Dist 一致。
2. 若仍有偏差，抓取 worker 输出日志和 AutoDoor 节点状态，重点看绑定窗口 hwnd、DPI scale、模板匹配坐标。
3. 把 AutoDoor 行为树项目的关键修复纳入可追踪流程；当前 `D:\AddFriend\Addfriend` 不在 git 仓库内。

中优先级：

1. 将手机号来源从 AutoDoor `preset_texts` 改为后端联系人列表/任务配置下发，避免每次用 AutoDoor 编辑器维护号码。
2. 为 worker 增加“只检测不点击”的诊断模式，输出识别到的模板位置、窗口 hwnd、DPI、截图区域。
3. 增加任务失败时的详细错误事件，例如窗口未找到、模板最高置信度、节点 id。
4. 打包前确认生产环境 Python 版本和 AutoDoor 依赖一致；当前本机 Python 是 3.10，AutoDoor 打包 `_internal` 多数为 cp311 pyd，worker 当前主要依赖源码目录和本机 site-packages。

低优先级：

1. 设置页增加“测试配置”按钮，验证 AutoDoor 源码、项目、编辑器、DPI、手机号池。
2. 清理或归档旧测试脚本 `scripts/test_autobot.py`。
3. 给 worker 补单元测试或快照测试，覆盖行为树补丁逻辑。

---

## 7. 下次会话建议入口

新会话先读：

1. `SESSION_STATE.md`
2. `scripts/platform_worker.py`
3. `desktop/src-tauri/src/lib.rs`
4. `desktop/src/TaskPanel.tsx`
5. `desktop/src/SettingsPage.tsx`

推荐第一步命令：

```powershell
cd D:\FriendAuto
git status --short
python -m py_compile scripts\platform_worker.py
cd desktop
npm run build
cd src-tauri
cargo check
```

真实联调前检查：

```powershell
# 确认 AutoDoor 项目第一条手机号是 11 位
python -c "import json; from pathlib import Path; raw=json.loads(Path(r'D:\AddFriend\Addfriend\tree.json').read_text(encoding='utf-8')); print(raw['nodes']['node_45']['config']['preset_texts'][0])"
```

---

## 8. 风险与注意事项

- `D:\AddFriend\Addfriend` 是仓库外资源，FriendAuto 的 git push 不会包含它。
- AutoDoor Dist 能点准但 FriendAuto 点偏时，优先排查 DPI 初始化、目标窗口 hwnd、同标题微信窗口、模板 `dpi_base`。
- 不要在 worker 运行副本里盲目清空 `window_hwnd/window_pid`；这样可能和 AutoDoor Dist 行为不一致。
- 如果同一台机器上存在多个“微信”窗口，标题匹配可能绑定错窗口；最稳的是在 AutoDoor 编辑器里重新选择目标窗口并保存行为树。
- 只有 `success` 事件会扣试用次数，`failed/invalid/error` 不应扣次。
