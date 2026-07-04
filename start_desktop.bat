@echo off
cd /d "%~dp0desktop"
set VITE_API_BASE=http://47.111.3.83:8001
npm run tauri dev
pause
