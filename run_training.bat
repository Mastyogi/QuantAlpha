@echo off
:: ============================================================
:: QuantAlpha — 24/7 Auto Training Runner (Windows)
:: Double-click karo ya Task Scheduler mein add karo
:: ============================================================
title QuantAlpha 24/7 Training System

cd /d "%~dp0"

echo.
echo ============================================================
echo   QuantAlpha 24/7 Continuous Improvement System
echo   %DATE% %TIME%
echo ============================================================
echo.

:: Python check
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ first.
    pause
    exit /b 1
)

:: Create logs directory
if not exist "logs" mkdir logs

:: Create models directory
if not exist "models" mkdir models

:: Install/update dependencies silently
echo [1/4] Checking dependencies...
pip install -r requirements.txt -q --no-warn-script-location 2>logs\pip_install.log
echo       Done.

:: Kill any existing instance on port 8000
echo [2/4] Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: Set PYTHONPATH
set PYTHONPATH=%~dp0

echo [3/4] Starting 24/7 training loop...
echo       Logs: logs\training_%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%.log
echo       Press Ctrl+C to stop.
echo.

:: Run with auto-restart on crash
:RESTART_LOOP
echo [%TIME%] Starting continuous_improvement_system.py ...

python continuous_improvement_system.py >> "logs\training_%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%.log" 2>&1

set EXIT_CODE=%errorlevel%

if %EXIT_CODE% == 0 (
    echo [%TIME%] Process exited cleanly. Restarting in 10s...
) else (
    echo [%TIME%] Process crashed (code %EXIT_CODE%). Restarting in 30s...
    timeout /t 30 /nobreak >nul
)

timeout /t 10 /nobreak >nul
goto RESTART_LOOP
