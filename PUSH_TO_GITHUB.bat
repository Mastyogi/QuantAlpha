@echo off
REM QuantAlpha - Push to GitHub Script
REM Run this from project root directory

echo ============================================================
echo QuantAlpha - GitHub Push Script
echo ============================================================
echo.

REM Check if we're in the right directory
if not exist "src\" (
    echo ERROR: Please run this script from the project root directory
    echo Current directory: %CD%
    pause
    exit /b 1
)

echo Step 1: Checking Git status...
git status
echo.

echo Step 2: Verifying .env is NOT in staging area...
git status | findstr ".env"
if %ERRORLEVEL% EQU 0 (
    echo WARNING: .env file detected in staging area!
    echo Removing .env from git tracking...
    git rm --cached .env
)
echo.

echo Step 3: Adding all files...
git add .
echo.

echo Step 4: Checking what will be committed...
git status
echo.

echo ============================================================
echo IMPORTANT: Verify that .env is NOT in the list above!
echo ============================================================
echo.
pause

echo Step 5: Committing changes...
git commit -m "Initial commit: QuantAlpha Trading Bot - AI-powered trading bot with Telegram integration - Multi-exchange support (Bitget, Binance) - XGBoost ML models with auto-tuning - Kelly Criterion position sizing - Adaptive risk management - Docker deployment ready - Complete VPS deployment guides"
echo.

echo Step 6: Setting main branch...
git branch -M main
echo.

echo Step 7: Adding remote (if not exists)...
git remote add origin https://github.com/Mastyogi/QuantAlpha.git 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Remote already exists, skipping...
)
echo.

echo Step 8: Pushing to GitHub...
git push -u origin main
echo.

if %ERRORLEVEL% EQU 0 (
    echo ============================================================
    echo SUCCESS! Code pushed to GitHub
    echo ============================================================
    echo.
    echo Repository: https://github.com/Mastyogi/QuantAlpha
    echo.
    echo Next steps:
    echo 1. Visit: https://github.com/Mastyogi/QuantAlpha
    echo 2. Verify .env is NOT visible
    echo 3. Check README.md is displayed
    echo 4. Add repository description and topics
    echo.
) else (
    echo ============================================================
    echo ERROR: Push failed
    echo ============================================================
    echo.
    echo Common issues:
    echo 1. Authentication failed - Use Personal Access Token
    echo 2. Remote already has content - Use: git push -f origin main
    echo 3. Network issues - Check internet connection
    echo.
)

pause
