# FriendAuto 部署文档

更新时间：2026-06-30  
适用项目路径：`D:\FriendAuto`

## 1. 项目组成

FriendAuto 由四部分组成：

| 模块 | 路径 | 技术栈 | 部署形态 |
|---|---|---|---|
| 后端 API | `server/` | FastAPI + SQLAlchemy + Alembic | 常驻 Web 服务，默认端口 `8001` |
| 管理后台 | `admin/` | React + TypeScript + Vite | 静态站点，可由 Nginx/IIS/静态托管服务部署 |
| Windows 桌面端 | `desktop/` | Tauri v2 + React + TypeScript + Rust | Windows 安装包或开发模式运行 |
| 自动化 worker | `scripts/platform_worker.py` | Python + AutoDoor 项目桥接 | 由桌面端本机启动，不是服务端进程 |

当前业务口径：

- 登录为邮箱 + 密码；注册、找回密码、改密使用 6 位邮箱验证码。
- 支付当前是人工充值：桌面端创建 `manual_wechat` 订单，管理后台人工确认收款后开通会员。
- `/payments/wechat/callback` 和 `/payments/alipay/callback` 只是 debug mock，不是正式微信/支付宝支付。
- 桌面端默认请求后端地址是 `http://127.0.0.1:8001`，正式发版前需要改成线上 API 地址或做可配置化。

## 2. 已验证环境

本机当前验证通过的环境：

```powershell
Python 3.10.8
Node.js v22.18.0
npm 10.9.3
rustc 1.96.0
cargo 1.96.0
```

建议环境：

- Python：3.10+，并确保能安装 `server/requirements.txt`。
- Node.js：LTS 或当前项目已验证的 Node 22。
- Rust：`desktop/src-tauri/Cargo.toml` 声明最低 `1.77.2`，建议使用 stable 最新版。
- Windows 桌面端：需要 Windows、PowerShell、Python、微信客户端、AutoDoor 源码/项目目录。

## 3. 本地开发启动

### 3.1 后端

```powershell
cd D:\FriendAuto\server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

也可以直接运行根目录脚本：

```powershell
cd D:\FriendAuto
.\start_server.bat
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

期望返回：

```json
{"status":"ok","app":"FriendAuto"}
```

### 3.2 管理后台

```powershell
cd D:\FriendAuto\admin
npm install
npm run dev
```

开发地址：`http://localhost:5174`

开发模式下，`admin/vite.config.ts` 会把 `/admin`、`/auth`、`/uploads` 代理到 `http://127.0.0.1:8001`。

默认管理员账号由后端 `seed.py` 创建：

```text
admin / admin123
```

### 3.3 桌面端

```powershell
cd D:\FriendAuto\desktop
npm install
npm run tauri dev
```

根目录快捷脚本：

```powershell
cd D:\FriendAuto
.\start_desktop.bat
```

桌面端默认连接：

```text
http://127.0.0.1:8001
```

该地址写在 `desktop/src/App.tsx` 的 `API_BASE` 常量里。正式发版前必须确认它指向线上后端。

## 4. 后端部署指南

### 4.1 环境变量

后端配置来源于 `server/app/core/config.py`，默认会读取当前工作目录下的 `.env`。生产部署建议工作目录固定为 `server/`，并创建：

```powershell
D:\FriendAuto\server\.env
```

推荐模板：

```env
APP_NAME=FriendAuto
DEBUG=false
DATABASE_URL=sqlite:///./friendauto.db
SECRET_KEY=replace-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_MINUTES=43200

SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=no-reply@example.com
SMTP_PASSWORD=replace-with-smtp-password
SMTP_FROM_NAME=FriendAuto

WECHAT_MCH_ID=
WECHAT_API_KEY=
ALIPAY_APP_ID=
ALIPAY_PRIVATE_KEY=
```

重点说明：

- `DEBUG=false`：生产必须关闭，否则验证码接口会返回 `dev_code`，且测试账号/支付 mock 行为会存在。
- `SECRET_KEY`：生产必须替换，不能使用默认 `change-me-in-production`。
- `DATABASE_URL`：默认 SQLite 会解析到 `server/friendauto.db`。如果改 PostgreSQL/RDS，需要先验证 SQLAlchemy URL、迁移脚本和运行权限。
- SMTP 未配置时，验证码邮件不会真正发送，用户注册/找回密码会卡住。
- 微信/支付宝字段目前只是预留；正式支付验签、回调幂等、订单同步尚未实现。

### 4.2 初始化数据库

进入后端目录：

```powershell
cd D:\FriendAuto\server
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="$pwd"
python -m alembic upgrade head
```

启动应用时，`app.main` 的 lifespan 会执行 `init_db()`：

- 创建缺失表。
- 对 SQLite 旧表补列。
- 初始化默认套餐。
- 如果没有管理员，则创建 `admin / admin123`。

生产注意：

- 首次上线后必须修改默认管理员密码，或用临时脚本替换默认账号。
- 建议把 Alembic 作为正式迁移入口，不要长期依赖 `seed.py` 补结构。
- SQLite 文件和 `uploads/` 都需要纳入备份。

### 4.3 启动服务

测试启动：

```powershell
cd D:\FriendAuto\server
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Windows 生产可使用 NSSM、Windows 服务、计划任务或进程守护工具托管上述命令。服务工作目录必须是：

```text
D:\FriendAuto\server
```

Linux 生产可使用 systemd，示例：

```ini
[Unit]
Description=FriendAuto API
After=network.target

[Service]
WorkingDirectory=/opt/FriendAuto/server
Environment=PYTHONPATH=/opt/FriendAuto/server
ExecStart=/opt/FriendAuto/server/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## 5. 管理后台部署指南

### 5.1 构建

如果管理后台与后端同域部署，并通过反向代理把 `/admin`、`/uploads` 等路径转到后端，可以不设置 `VITE_API_BASE`：

```powershell
cd D:\FriendAuto\admin
npm ci
npm run build
```

如果管理后台和后端不同域，需要指定 API 地址：

```powershell
cd D:\FriendAuto\admin
npm ci
$env:VITE_API_BASE="https://api.example.com"
npm run build
```

构建产物：

```text
D:\FriendAuto\admin\dist
```

### 5.2 Nginx 示例

同域部署示例：

```nginx
server {
    listen 443 ssl;
    server_name admin.example.com;

    root /opt/FriendAuto/admin/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8001/admin/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /uploads/ {
        proxy_pass http://127.0.0.1:8001/uploads/;
    }

    location /health {
        proxy_pass http://127.0.0.1:8001/health;
    }
}
```

如果还要通过同一域名服务桌面端 API，需要按实际客户端请求补齐 `/auth`、`/devices`、`/me`、`/plans`、`/orders`、`/tasks`、`/contacts`、`/feedback`、`/payments` 等后端路径代理。

## 6. 桌面端打包与发版

### 6.1 发版前确认

必须确认：

- `desktop/src/App.tsx` 中 `API_BASE` 指向线上 API，例如 `https://api.example.com`。
- 后端已启用 HTTPS，桌面端能访问 `/health`、`/auth/login`、`/me/status`。
- 客户机器已准备 Python 和 AutoDoor 运行依赖。
- 客户机器上安装并登录微信客户端。
- AutoDoor 项目目录包含 `project.json` 和 `tree.json`。

### 6.2 构建安装包

```powershell
cd D:\FriendAuto\desktop
npm ci
npm run build
npm run tauri build
```

常见产物位置：

```text
desktop\src-tauri\target\release\bundle\
```

### 6.3 客户端运行依赖

桌面端运行时会读取/写入：

```text
%APPDATA%\FriendAuto\auth.json
%APPDATA%\FriendAuto\autodoor.json
%APPDATA%\FriendAuto\runs\
%APPDATA%\FriendAuto\automation.lock
%APPDATA%\FriendAuto\clipboard.lock
```

默认 AutoDoor 路径：

```text
D:\AddFriend\autodoor_behavior_tree
D:\AddFriend\Addfriend
D:\AddFriend\autodoor_behavior_tree\dist\autodoor-behaviortree-1.6.0\autodoor-behaviortree-1.6.0.exe
```

用户可在应用内配置 AutoDoor 源码目录、项目目录和编辑器路径。保存时会校验：

- AutoDoor 源码目录存在。
- 项目目录存在。
- 项目目录包含 `project.json` 和 `tree.json`。
- 如填写编辑器路径，该路径必须存在。

## 7. 上线前检查

项目自带检查入口：

```powershell
cd D:\FriendAuto
powershell -ExecutionPolicy Bypass -File scripts\check_all.ps1
```

当前已验证通过的检查项：

- 后端 Python compile。
- `scripts/platform_worker.py` 语法检查。
- 桌面端 `npm run build`。
- 桌面端 `npm run lint`。
- 管理后台 `npm run build`。

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

## 8. 生产注意事项

### 安全

- 必须设置 `DEBUG=false`。
- 必须替换 `SECRET_KEY`。
- 必须修改默认管理员 `admin / admin123`。
- 当前 CORS 在 `server/app/main.py` 中是 `allow_origins=["*"]`，生产公开部署前建议改成可信域名白名单。
- 不要把支付密钥、SMTP 密码、数据库密码提交到仓库。
- 桌面端不要保存支付密钥，也不要在桌面端裁决会员、试用、设备或订单状态。

### 数据

- 默认 SQLite 适合早期/单机部署；多人并发和生产长期运行建议迁移到 PostgreSQL/RDS。
- SQLite 部署时，必须备份 `server/friendauto.db`。
- 反馈图片上传目录为 `uploads/feedback`，必须备份整个 `server/uploads/`。
- 升级前先备份数据库和上传目录，再执行 Alembic。

### 支付

- 当前正式可用流程是人工充值 + 管理后台确认收款。
- mock 支付回调只在 `DEBUG=true` 下可用，不能作为正式支付能力。
- 接入微信/支付宝正式支付前，需要补齐：签名验签、回调幂等、订单状态同步、失败重试、审计日志和密钥管理。

### 邮件验证码

- `SMTP_HOST` 为空时不会发送邮件。
- `DEBUG=true` 时验证码接口会返回 `dev_code`，生产必须关闭。
- 注册/找回密码依赖邮箱验证码，SMTP 是生产必配项。

### 桌面自动化

- worker 在用户本机运行，不在服务器运行。
- 客户端需要能启动 `python` 命令。
- 多微信窗口任务依赖窗口绑定，微信窗口、PID、HWND 变化后可能需要重新绑定。
- AutoDoor 项目结构变更后，要重新验证 `daily_limit=1/2`、窗口绑定、成功/失败/无效结果统计。
- Windows 安全软件可能拦截自动化、剪贴板、键鼠控制或子进程启动，需要加入信任。

### 运维

- 后端建议放在反向代理后面，仅对外暴露 HTTPS。
- `/health` 可作为健康检查路径。
- 后端日志、进程守护和异常告警需要由部署环境补齐。
- 每次发版记录：代码版本、数据库迁移版本、桌面端版本、后端地址、管理员账号处理状态。

## 9. 推荐发布流程

1. 拉取代码并确认分支/提交。
2. 备份数据库和 `uploads/`。
3. 安装或更新后端依赖。
4. 执行 `python -m alembic upgrade head`。
5. 检查 `.env`，确认 `DEBUG=false`、`SECRET_KEY`、SMTP。
6. 启动或重启后端服务。
7. 请求 `/health` 确认后端正常。
8. 构建并部署 `admin/dist`。
9. 用管理员登录后台，确认用户、订单、套餐页正常。
10. 修改桌面端线上 `API_BASE`，构建 Tauri 安装包。
11. 在干净 Windows 机器安装桌面端，完成登录、注册/验证码、订单创建、任务启动前检查、反馈上传测试。
12. 发布安装包，并记录版本和回滚方案。

## 10. 常见问题

### 管理后台登录失败

- 确认后端服务正在运行。
- 确认管理后台请求能访问 `/admin/login`。
- 首次部署确认数据库中已创建管理员。
- 如果还是默认密码，先完成登录后立即更换或用脚本更新密码。

### 用户收不到验证码

- 检查 `.env` 中 SMTP 配置。
- 检查服务日志中的 `Failed to send email`。
- 确认 `DEBUG=false` 后不会再依赖 `dev_code`。

### 桌面端连不上服务

- 检查 `desktop/src/App.tsx` 的 `API_BASE` 是否仍是 `http://127.0.0.1:8001`。
- 检查线上后端 HTTPS 证书和防火墙。
- 检查 `/health` 是否可从客户机器访问。

### 反馈图片打不开

- 检查 `server/uploads/feedback` 是否存在。
- 检查反向代理是否代理 `/uploads/`。
- 检查上传目录是否被部署流程清空。

### AutoDoor 任务启动失败

- 确认客户机器安装 Python，并且命令行能执行 `python --version`。
- 确认 AutoDoor 源码目录和项目目录配置正确。
- 确认项目目录包含 `project.json` 和 `tree.json`。
- 确认微信已登录，目标微信窗口已绑定。
- 查看桌面端任务日志中的 worker 错误信息。
