# FriendAuto — 会话摘要

> 生成日期：2026-06-26

---

## 架构总览

```
FriendAuto/
├── desktop/          # Tauri v2 桌面客户端 (React 19 + TypeScript)
│   └── src/
│       ├── App.tsx           # 根组件，auth 状态管理，路由分发
│       ├── App.css           # CSS 变量系统 + 登录页样式
│       ├── LoginPage.tsx     # 登录/注册/找回密码
│       ├── MainPage.tsx      # 主页面三栏布局 (TitleBar/空白 + Sidebar + Content)
│       ├── MainPage.css      # 主页面全部样式 (sidebar/hero/task-card/payment)
│       ├── TaskPanel.tsx     # 加好友任务面板（配置/启停/日志）
│       ├── PaymentModal.tsx  # 会员充值弹窗（新设计：联系工作人员充值）
│       ├── index.css         # 全局 reset
│       └── main.tsx          # React 入口
│   └── src-tauri/            # Rust 后端 (机器码/任务管理/auth 持久化)
├── server/                   # FastAPI 后端 (Python)
├── admin/                    # 后台管理面板
├── scripts/                  # 自动加好友 Python 脚本
└── docs/                     # 项目文档
```

---

## 已决策的关键设计

| 决策 | 结论 |
|------|------|
| **标题栏** | 使用 OS 原生标题栏（`decorations: true`），无自定义按钮 |
| **设备绑定** | 一台设备绑定多个账号，一个账号只能绑定一台设备 |
| **注销方式** | 首页 content-header 右上角 `[user@email] [退出]`，退出→清 token→登录页 |
| **窗口尺寸** | 登录页 900×720，主页面 `min(1370px, calc(100vw - 56px))` × `min(1032px, calc(100vh - 42px))` |
| **会员充值** | "联系工作人员充值"→弹出微信二维码浮层，不经过 API 支付流程 |
| **侧边栏** | 8 个导航项做 UI 占位（`首页/自动加好友/联系人管理/任务记录/客服/反馈/我的/设置`），暂不挂路由，支持折叠 276↔88px |
| **轮播横幅** | 纯 CSS 装饰图，暂不做 JS 交互 |
| **CSS 变量** | 统一以 `--bg` / `--panel` / `--sidebar-bg` / `--blue` / `--green` / `--orange` 等命名 |

---

## 已完成部分

### Phase 1 — 布局基础架构 ✅
- [x] `App.css`：替换 CSS 变量为新设计系统，保留登录页独有样式
- [x] `MainPage.tsx`：三栏布局（TitleBar 空白 + Sidebar + Content），嵌入 TaskPanel
- [x] `MainPage.css`：titlebar / sidebar（折叠/展开）/ hero-panel（纯 CSS 装饰图）/ task-card 全部新样式
- [x] 登录页标题栏类名修复（`.titlebar` / `.win-btn` 恢复为顶层类名）

### PaymentModal 新设计 ✅
- [x] 支付改为 "联系工作人员充值" → 微信二维码浮层
- [x] 去掉支付宝选项，仅保留微信
- [x] 价格标签增加省钱提示（省 ¥400 / 省 ¥2800）
- [x] 去掉 `onPaid` 回调，改用 QR 模态框

### 注销 & 用户信息 ✅
- [x] `App.tsx` 恢复 `handleLogout`
- [x] `MainPage content-header` 增加 `[user@email] [退出]`

### 构建修复 ✅
- [x] React 19 `useRef` 必须传初始值
- [x] 清理各处未使用变量（`noUnusedLocals` / `noUnusedParameters`）

### 设备绑定（上一会话）✅
- [x] 后端绑定时 `machine_code` 唯一约束改为 `account_id + machine_code` 联合唯一
- [x] 一个设备可绑定多个账号，一个账号只能绑一台设备
- [x] API 测试验证通过

---

## 待办事项

### Phase 2 — 侧边栏路由
- [ ] 侧边栏 8 个导航项挂真实路由（React Router 或状态切换）
- [ ] 折叠/展开动效完善
- [ ] 当前页高亮持久化

### Phase 3 — 轮播横幅
- [ ] 轮播 JS 交互（多张 slide 切换）
- [ ] 自动轮播 + 指示器

### Phase 4 — 状态对接
- [ ] 会员状态、试用次数等数据动态刷新
- [ ] 侧边栏导航对应页面内容填充

---

## 重要文件修改记录

| 文件 | 最近修改内容 |
|------|-------------|
| `desktop/src/App.css` | CSS 变量重命名、登录页标题栏类名修复 |
| `desktop/src/App.tsx` | 恢复 `handleLogout`，传给 MainPage |
| `desktop/src/LoginPage.tsx` | 删除自定义 TitleBar 组件，build-fix（useRef + 未使用变量） |
| `desktop/src/MainPage.tsx` | 新三栏布局（sidebar/hero/task-card），删除自定义标题栏，增加 email+退出 |
| `desktop/src/MainPage.css` | 全部新样式 ~1100 行（sidebar/hero/task-card/payment/QR 等） |
| `desktop/src/PaymentModal.tsx` | 新设计（联系工作人员+QR 浮层），仅微信支付 |
| `desktop/src/TaskPanel.tsx` | build-fix：未使用变量清理 |
| `desktop/src-tauri/tauri.conf.json` | 原生标题栏（`decorations` 未设置，默认 true） |
| `desktop/src-tauri/capabilities/default.json` | 保持 core:default + shell:default |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 桌面框架 | Tauri v2 (Rust + WebView) |
| 前端 | React 19 + TypeScript |
| 构建 | Vite 8 |
| CSS | 纯 CSS + CSS Variables + color-mix |
| 后端 | FastAPI (Python) |
| 数据库 | SQLite (via SQLAlchemy + Alembic) |
| 窗口 | OS 原生标题栏（无自定义装饰） |
