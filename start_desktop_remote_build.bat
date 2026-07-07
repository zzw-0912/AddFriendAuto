@echo off
setlocal
cd /d "%~dp0desktop"

set VITE_API_BASE=http://47.111.3.83:8001

echo Building FriendAuto Desktop for remote API...
echo API: %VITE_API_BASE%
npm run build
pause
