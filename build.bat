@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Build Script
REM ============================================================
REM This script builds the Windows executable for BAB-Cloud
REM Requires Python 3.13 (pythonnet compatibility)
REM ============================================================

echo ========================================
echo BAB-Cloud PrintHub - Build Script
echo ========================================
echo.

REM ============================================================
REM Step 1: Check Python 3.13
REM ============================================================
echo [1/8] Verifying Python 3.13...
py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.13 is required
    echo Please install Python 3.13 and try again
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
py -3.13 --version
echo.

REM ============================================================
REM Step 2: Check/Install PyInstaller
REM ============================================================
echo [2/8] Checking PyInstaller...
py -3.13 -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    py -3.13 -m pip install pyinstaller==6.10.0
) else (
    echo PyInstaller is installed
)
echo.

REM ============================================================
REM Step 3: Clean Previous Builds
REM ============================================================
echo [3/8] Cleaning previous build artifacts...
if exist build (
    echo Removing build folder...
    rmdir /s /q build
)
if exist dist (
    echo Removing dist folder...
    rmdir /s /q dist
)
echo Clean complete
echo.

REM ============================================================
REM Step 4: Build Executable
REM ============================================================
echo [4/8] Building BAB-Cloud executable...
echo This may take 2-3 minutes...
py -3.13 -m PyInstaller --clean --noconfirm bab_cloud.spec
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)
echo Build successful!
echo.

REM ============================================================
REM Step 5: Transaction Folders (Created On-Demand)
REM ============================================================
echo [5/8] Transaction folders will be created automatically...
echo Each software integration creates its own folder when started
echo.

REM ============================================================
REM Step 6: Copy Configuration Files
REM ============================================================
echo [6/8] Copying configuration files...
copy /y "bridge\config.json" "dist\BAB_Cloud\" >nul
if exist "bridge\odoo_credentials_encrypted.json" (
    echo Copying Odoo credentials...
    copy /y "bridge\odoo_credentials_encrypted.json" "dist\BAB_Cloud\" >nul
)
echo Configuration files copied
echo.

REM ============================================================
REM Step 7: Copy Tools Folder
REM ============================================================
echo [7/8] Copying tools folder...
if exist tools (
    mkdir "dist\BAB_Cloud\tools" 2>nul
    xcopy /y /i "tools\*.py" "dist\BAB_Cloud\tools\" >nul
    echo Tools copied
) else (
    echo No tools folder found - skipping
)
echo.

REM ============================================================
REM Step 8: Create README in dist
REM ============================================================
echo [8/8] Creating distribution README...
(
echo BAB-Cloud PrintHub v2026
echo ========================
echo.
echo Executable: BAB_Cloud.exe
echo.
echo First Run:
echo 1. Edit config.json to set your POS system and printer
echo 2. For Odoo: Place odoo_credentials_encrypted.json in this folder
echo 3. For TCPOS: Set transactions_folder path in config.json
echo 4. Run BAB_Cloud.exe
echo.
echo The application will run in the system tray.
echo Right-click the tray icon for options.
echo.
echo Logs are written to log.log in this folder.
echo.
echo For support: https://github.com/solutech/bab-cloud
) > "dist\BAB_Cloud\README.txt"
echo Distribution README created
echo.

REM ============================================================
REM Build Complete
REM ============================================================
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Executable location:
echo   dist\BAB_Cloud\BAB_Cloud.exe
echo.
echo Distribution size:
dir "dist\BAB_Cloud" | find "File(s)"
echo.
echo To test: cd dist\BAB_Cloud ^&^& BAB_Cloud.exe
echo To deploy: Copy the entire BAB_Cloud folder
echo.
pause
