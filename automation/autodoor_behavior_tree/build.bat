@echo off
chcp 65001 >nul
echo ========================================
echo AutoDoor Behavior Tree - Unified Build
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python environment...
python --version
if errorlevel 1 (
    echo Error: Python not found!
    pause
    exit /b 1
)

echo.
echo Checking required modules...
python -c "import customtkinter; import rapidocr; import pygame; import PIL; print('All modules OK')"
if errorlevel 1 (
    echo Error: Required modules not installed!
    echo Please run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo Generating build info from build_config.json...
python generate_build_info.py
if errorlevel 1 (
    echo Warning: Failed to generate build info, using defaults
)

echo.
echo Starting PyInstaller build (Unified version)...
pyinstaller autodoor_bt.spec --clean

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo Output: dist\autodoor-behaviortree-*\
echo ========================================
pause
