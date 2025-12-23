@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Run Script
REM ============================================================
REM Start BAB PrintHub with Python 3.13
REM ============================================================

echo Starting BAB-Cloud PrintHub v1.3...
echo.

cd /d "%~dp0"
py -3.13 -m src.fiscal_printer_hub

pause
