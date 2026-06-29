# FriendAuto Desktop

FriendAuto 桌面端基于 Tauri v2 + React + TypeScript + Vite。它负责用户界面、登录态、本机配置、任务启动、AutoDoor worker 事件展示和结果上报；会员、试用、设备和支付裁决均由后端完成。

## 当前功能

- 邮箱 + 密码登录。
- 注册和找回密码使用 6 位邮箱验证码。
- 首页、用户教程、客服二维码、反馈、我的页面。
- Profile 中包含账号信息、设备信息、密码修改和多账号切换。
- 任务卡片按套餐渲染，支持启动/停止 AutoDoor worker。
- 当前支付为人工充值：创建 `manual_wechat` 订单并等待后台确认。
- 微信支付和支付宝支付为后续计划接入能力，当前不是正式支付通道。

## 常用命令

```powershell
cd D:\FriendAuto\desktop
npm install
npm run dev
npm run build
npm run lint
npm run tauri dev
```

## 后端依赖

桌面端默认访问：

```text
http://127.0.0.1:8001
```

启动后端：

```powershell
cd D:\FriendAuto\server
$env:PYTHONPATH="$pwd"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Tauri

开发启动：

```powershell
cd D:\FriendAuto\desktop
npm run tauri dev
```

构建安装包：

```powershell
cd D:\FriendAuto\desktop
npm run tauri build
```

## 联调账号

- 用户测试：`test@friendauto.com / 888888`
- 管理员：`admin / admin123`

## 注意事项

- 不要在桌面端裁决会员、试用、设备或支付状态。
- 不要把支付密钥放入桌面端。
- `SettingsPage.tsx` 当前是 legacy，不在导航。
- 多账号 token 当前保存在 localStorage，后续可迁入 Tauri 原生存储。
