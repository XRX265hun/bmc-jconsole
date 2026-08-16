@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python 3.10 or newer is required.
    echo Install it from https://www.python.org/downloads/ then run this file again.
    echo Java 8 with Web Start is also required for the actual console window.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create .venv
        pause
        exit /b 1
    )
)

echo Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo pip install failed
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m bmc_jconsole
if errorlevel 1 pause
