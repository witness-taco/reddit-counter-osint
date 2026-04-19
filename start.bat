@echo off
setlocal

set SCRIPT_NAME=V4.1_hardened_reddit_active_learner.py
set VENV_DIR=venv

echo ================================================
echo   Reddit Content Retention Manager - Launcher   
echo ================================================

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Error: Python is not installed or not in your system PATH.
    pause
    exit /b 1
)

:: 2. Check if the virtual environment exists; if not, create it
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [+] No virtual environment found. Creating one in '.\%VENV_DIR%'...
    python -m venv %VENV_DIR%
    echo [+] Virtual environment created successfully.
)

:: 3. Activate the virtual environment
echo [+] Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat

:: 4. Install/Upgrade dependencies
echo [+] Checking dependencies...
python -m pip install --upgrade pip -q
python -m pip install nodriver -q
echo [+] Dependencies are up to date.

:: 5. Run the main application
echo ================================================
echo [+] Launching %SCRIPT_NAME%...
echo ================================================
python %SCRIPT_NAME%

:: 6. Deactivate the environment after the script finishes
call deactivate
echo [+] Session ended. Virtual environment deactivated.
pause