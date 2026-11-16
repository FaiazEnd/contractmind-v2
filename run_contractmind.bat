@echo off
setlocal
cd /d "%~dp0"

echo ================================================================================
echo ContractMind v2.0 - 1-Click Local Studio Launcher
echo ================================================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ is required but was not found on PATH.
    pause
    exit /b 1
)

echo [1/3] Checking Python dependencies...
python -m pip install --quiet -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo [WARN] Some optional packages did not install cleanly; continuing with core runtime...
)

echo [2/3] Syncing frontend static studio...
if not exist "frontend\public" mkdir "frontend\public"
copy /Y "backend\static\index.html" "frontend\public\index.html" >nul

echo [3/3] Launching ContractMind v2.0 at http://localhost:8000 ...
python launch.py
pause
