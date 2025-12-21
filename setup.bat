@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Environment Setup Script
REM ============================================================
REM This script sets up the development environment
REM ============================================================

echo ========================================
echo BAB-Cloud PrintHub - Setup
echo ========================================
echo.

REM Check Python 3.13
echo [1/3] Checking Python 3.13...
py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.13 is required
    echo Please install Python 3.13 from https://www.python.org/downloads/
    pause
    exit /b 1
)
py -3.13 --version
echo.

REM Install dependencies
echo [2/3] Installing dependencies...
echo This may take a few minutes...
py -3.13 -m pip install --upgrade pip
py -3.13 -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully
echo.

REM Create initial directories
echo [3/3] Creating initial directories...
cd bridge
if not exist "odoo-transactions" mkdir "odoo-transactions"
if not exist "tcpos-transactions" mkdir "tcpos-transactions"
if not exist "simphony-transactions" mkdir "simphony-transactions"
if not exist "quickbooks-transactions" mkdir "quickbooks-transactions"
cd ..
echo Directories created
echo.

echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit bridge\config.json to configure your POS system
echo 2. For Odoo: Run tools\update_odoo_credentials.py
echo 3. Test with: run.bat
echo 4. Build with: build.bat
echo.
pause
