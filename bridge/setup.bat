@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Setup Script
REM ============================================================
REM Install dependencies and prepare environment
REM ============================================================

echo.
echo ============================================================
echo BAB-Cloud PrintHub v1.4 - Setup Script
echo ============================================================
echo.
echo This script will:
echo 1. Check for Python 3.13
echo 2. Create a virtual environment
echo 3. Install all required dependencies
echo 4. Verify installation
echo.

pause

REM Change to bridge directory
cd /d "%~dp0"

REM Check if Python 3.13 is available
echo [1/6] Checking for Python 3.13...
py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.13 is not installed or not in PATH
    echo.
    echo Please install Python 3.13 from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

py -3.13 --version
echo Python 3.13 found!
echo.

REM Remove old virtual environment if exists
if exist "venv" (
    echo [2/6] Removing old virtual environment...
    rmdir /S /Q venv
    echo.
)

REM Create virtual environment
echo [2/6] Creating virtual environment...
py -3.13 -m venv venv
if errorlevel 1 (
    echo.
    echo ERROR: Failed to create virtual environment!
    echo.
    pause
    exit /b 1
)
echo Virtual environment created successfully!
echo.

REM Activate virtual environment
echo [3/6] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Upgrade pip
echo [4/6] Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install dependencies
echo [5/6] Installing dependencies from requirements.txt...
echo This may take several minutes...
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies!
    echo.
    pause
    exit /b 1
)
echo.

REM Verify installation
echo [6/6] Verifying installation...
echo.
python -c "import pyserial; import pywebview; import pystray; import pythonnet; import cryptography; import requests; import psutil; import xmltodict; print('All core packages imported successfully!')"
if errorlevel 1 (
    echo.
    echo WARNING: Some packages may not have been installed correctly!
    echo Please check the error messages above.
    echo.
) else (
    echo.
    echo ============================================================
    echo Setup completed successfully!
    echo ============================================================
    echo.
    echo Next steps:
    echo 1. Edit config.json to configure your printer and POS software
    echo 2. Run "run.bat" to start BAB PrintHub
    echo 3. Run "build.bat" to create an executable (optional)
    echo.
)

pause
