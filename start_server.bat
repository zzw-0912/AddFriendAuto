@echo off
cd /d "%~dp0server"
set PYTHONPATH=%~dp0server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
pause
