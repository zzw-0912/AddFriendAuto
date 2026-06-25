# FriendAuto — Project Snapshot

## Git
- Remote: `https://github.com/zzw-0912/AddFriendAuto.git`
- Branch: `master` — 3 commits ahead (stages 0–2 + boilerplate), all pushed

## Architecture
- **desktop/** — Tauri v2 + React + TypeScript + Vite
- **server/** — FastAPI + SQLAlchemy (SQLite dev / PostgreSQL prod)
- **scripts/** — Python automation scripts

## Dev Commands
| Component | Command |
|-----------|---------|
| Backend | `cd server; $env:PYTHONPATH="$pwd"; uvicorn app.main:app --reload --port 8001` |
| Desktop | `cd desktop; npm run tauri dev` |
| DB reset | Delete `server/friendauto.db` |
| Kill port | `Stop-Process -Id (netstat -ano | findstr ':8001' | Select-Object -First 1) -replace '.*\s+(\d+)$','$1' -Force` |

## Test Account
- `test@friendauto.com` / code `888888` — skips device binding, no SMTP needed

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/auth/send-code` | Send verification code |
| POST | `/auth/login` | Login/Register + device bind |
| POST | `/auth/refresh` | Refresh token |
| POST | `/devices/bind` | Bind device |
| GET | `/devices/current` | Current device info |
| GET | `/me/status` | Membership + trial status |
| GET | `/plans` | List plans |
| POST | `/orders` | Create order |
| GET | `/orders/{id}` | Get order status |
| POST | `/payments/wechat/callback` | Mock WeChat payment callback |
| POST | `/payments/alipay/callback` | Mock Alipay payment callback |

## DB Tables (12)
`users`, `verification_codes`, `devices`, `memberships`, `plans`, `orders`,
`payments`, `email_configs`, `trial_quotas`, `friend_tasks`, `task_results`,
`task_logs`

## Plans (seeded)
| Name | Price | Duration |
|------|-------|----------|
| 月度会员 | ¥29.9 | 30 days |
| 季度会员 | ¥79.9 | 90 days |
| 年度会员 | ¥299.9 | 365 days |

## Business Rules
- New users auto-get 20 trial quota
- Login auto-binds device; second device gets 403
- Test account `test@friendauto.com` skips binding
- Membership stacking: new period starts after existing active period
- Payment mocked via `POST /payments/wechat/callback?order_no=...`

## Key Files
- `server/app/main.py` — App entry, router registration
- `server/app/services/auth_service.py` — Auth logic (send-code, login, trial, binding)
- `server/app/services/payment_service.py` — Payment mock + membership activation
- `server/app/services/status_service.py` — User status (membership + trial)
- `desktop/src/LoginPage.tsx` — 3-tab login UI
- `desktop/src/MainPage.tsx` — Main UI with status bar
- `desktop/src/PaymentModal.tsx` — Plan selection + payment modal
- `desktop/src-tauri/src/lib.rs` — Rust commands (machine code, token, script)

## Next Stage (Stage 3)
Task management: `POST /tasks/start-check`, `POST /tasks/{id}/results`, real-time logs, script integration.
