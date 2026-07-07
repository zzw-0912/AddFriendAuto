@echo off
cd /d "%~dp0server"
set PYTHONPATH=%~dp0server
echo Starting FriendAuto API...
echo API: http://0.0.0.0:8001
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
pause
