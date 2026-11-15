@echo off
setlocal
title ContractMind v2.0 — Neo-Legal Studio Launcher

echo [ContractMind] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required and was not found on PATH.
    pause
    exit /b 1
)

echo [ContractMind] Installing / verifying backend dependencies...
python -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [WARN] Some optional dependencies could not be installed; continuing with core stack.
)

echo [ContractMind] Launching ContractMind v2.0 Studio on http://localhost:8000 ...
python launch.py
endlocal
