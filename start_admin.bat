@echo off
cd /d "%~dp0admin"
set VITE_API_BASE=http://47.111.3.83:8001
echo Starting FriendAuto Admin Panel...
echo API: http://47.111.3.83:8001
echo Admin panel is listening on 0.0.0.0:5174
echo Local: http://localhost:5174
echo LAN/Public: http://47.111.3.83:5174
start http://localhost:5174
npm run dev -- --host 0.0.0.0
pause
