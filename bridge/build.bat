@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Build Script
REM ============================================================
REM Build executable with PyInstaller
REM ============================================================

echo.
echo ============================================================
echo BAB-Cloud PrintHub v1.4 - Build Script
echo ============================================================
echo.

REM Change to bridge directory
cd /d "%~dp0"

REM Check if Python 3.13 is available
py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.13 is not installed or not in PATH
    echo Please install Python 3.13 from python.org
    pause
    exit /b 1
)

echo [1/5] Checking Python 3.13...
py -3.13 --version
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

echo [3/5] Cleaning previous build artifacts...
if exist "dist" rmdir /S /Q dist
if exist "build" rmdir /S /Q build
if exist "*.spec" del /Q *.spec
echo.

echo [4/5] Building executable with PyInstaller...
echo This may take several minutes...
echo.

pyinstaller ^
    --name="BAB-PrintHub-v1.4" ^
    --onefile ^
    --windowed ^
    --icon=logo.png ^
    --add-data="logo.png;." ^
    --hidden-import=clr ^
    --hidden-import=pythonnet ^
    --hidden-import=pywebview ^
    --hidden-import=pystray ^
    --hidden-import=PIL ^
    --hidden-import=serial ^
    --hidden-import=cryptography ^
    --hidden-import=requests ^
    --hidden-import=psutil ^
    --hidden-import=xmltodict ^
    --collect-all=pythonnet ^
    --collect-all=pywebview ^
    src\fiscal_printer_hub.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo [5/5] Copying config.json to dist folder...

REM Check if executable exists
if exist "dist\BAB-PrintHub-v1.4.exe" (
    echo Executable created: dist\BAB-PrintHub-v1.4.exe
    echo Size:
    dir "dist\BAB-PrintHub-v1.4.exe" | findstr "BAB-PrintHub"
    echo.

    REM Copy config.json to dist folder
    if exist "config.json" (
        copy /Y config.json dist\config.json >nul
        echo Copied config.json to dist folder
    ) else (
        echo WARNING: config.json not found! You'll need to create one in the dist folder.
    )
    echo.
) else (
    echo ERROR: Executable was not created!
    exit /b 1
)

echo ============================================================
echo Build completed! Executable is ready in the dist folder.
echo ============================================================
echo.

pause
