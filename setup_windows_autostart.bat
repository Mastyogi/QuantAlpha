@echo off
REM Setup Windows Task Scheduler for Auto-Start
REM Run this as Administrator

echo ============================================================
echo QuantAlpha Trading Bot - Windows Auto-Start Setup
echo ============================================================
echo.

REM Get current directory
set SCRIPT_DIR=%~dp0
set PYTHON_PATH=python
set SCRIPT_PATH=%SCRIPT_DIR%keep_bot_running.py

echo Script Directory: %SCRIPT_DIR%
echo Python Path: %PYTHON_PATH%
echo Script Path: %SCRIPT_PATH%
echo.

REM Create scheduled task
echo Creating scheduled task...
schtasks /create /tn "QuantAlpha Trading Bot" /tr "%PYTHON_PATH% %SCRIPT_PATH%" /sc onstart /ru "%USERNAME%" /rl highest /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCESS! Bot will auto-start on Windows boot
    echo ============================================================
    echo.
    echo To manage:
    echo   - Start now: schtasks /run /tn "QuantAlpha Trading Bot"
    echo   - Stop: taskkill /f /im python.exe
    echo   - Remove: schtasks /delete /tn "QuantAlpha Trading Bot" /f
    echo.
) else (
    echo.
    echo ERROR: Failed to create task
    echo Please run this script as Administrator
    echo.
)

pause
