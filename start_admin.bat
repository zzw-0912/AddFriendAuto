@echo off
cd /d "%~dp0admin"
echo Starting FriendAuto Admin Panel...
echo Admin panel is listening on 0.0.0.0:5174
echo Local: http://localhost:5174
echo LAN/Public: http://YOUR_SERVER_IP:5174
start http://localhost:5174
npm run dev -- --host 0.0.0.0
pause
