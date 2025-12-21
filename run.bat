@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Development Run Script
REM ============================================================
REM This script runs the application in development mode
REM ============================================================

echo ========================================
echo BAB-Cloud PrintHub - Development Mode
echo ========================================
echo.

REM Check Python 3.13
py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.13 is required
    echo Please install Python 3.13
    pause
    exit /b 1
)

REM Change to bridge directory
cd bridge

REM Run the application
echo Starting BAB-Cloud PrintHub...
echo Press Ctrl+C to stop
echo.
py -3.13 fiscal_printer_hub.py

REM Return to root
cd ..

pause
