@echo off
cd /d "%~dp0admin"
echo Starting FriendAuto Admin Panel...
echo Open http://localhost:5174 in your browser
start http://localhost:5174
npm run dev
pause
