@echo off
setlocal
echo ====================================================
echo   ContractMind v2.0 - 1-Click Local Studio Launcher
echo ====================================================

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ not found on PATH.
    pause
    exit /b 1
)

echo [1/2] Verifying Python dependencies...
python -m pip install -q -r backend\requirements.txt

echo [2/2] Launching ContractMind v2.0 on http://localhost:8000 ...
python launch.py

endlocal
