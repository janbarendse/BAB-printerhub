@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Build Script
REM ============================================================
REM Build executable with PyInstaller
REM ============================================================

echo.
echo ============================================================
echo BAB-Cloud PrintHub v1.4.2 - Build Script
echo ============================================================
echo.

REM Change to bridge directory
cd /d "%~dp0"
set "ROOT_DIR=%~dp0"
set "LOGO_PATH=%ROOT_DIR%logo.png"

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
if exist "*.spec" del /Q *.spec
echo.

REM Use workspace subfolders for build artifacts
set "BUILD_TAG=%RANDOM%%RANDOM%"
set "WORK_DIR=build\pyi-work-%BUILD_TAG%"
set "DIST_DIR=build\pyi-dist-%BUILD_TAG%"
set "SPEC_DIR=build\pyi-spec-%BUILD_TAG%"

if not exist "build" mkdir build
mkdir "%WORK_DIR%" "%DIST_DIR%" "%SPEC_DIR%"

REM Ensure write permissions in build folders
attrib -R /S /D "build" >nul 2>&1
echo Using build tag: %BUILD_TAG%

REM Prepare dist folder without wiping runtime payloads
if not exist "dist" mkdir dist
attrib -R /S /D "dist" >nul 2>&1

REM Verify we can rename/delete in build + dist (PyInstaller needs this)
set "PERM_TEST_BUILD=build\.perm_test.tmp"
set "PERM_TEST_DIST=dist\.perm_test.tmp"
echo test> "%PERM_TEST_BUILD%" 2>nul
if not exist "%PERM_TEST_BUILD%" goto :perm_fail
ren "%PERM_TEST_BUILD%" ".perm_test2.tmp" >nul 2>&1
if errorlevel 1 goto :perm_fail
del /F /Q "build\.perm_test2.tmp" >nul 2>&1
if exist "build\.perm_test2.tmp" goto :perm_fail

echo test> "%PERM_TEST_DIST%" 2>nul
if not exist "%PERM_TEST_DIST%" goto :perm_fail
ren "%PERM_TEST_DIST%" ".perm_test2.tmp" >nul 2>&1
if errorlevel 1 goto :perm_fail
del /F /Q "dist\.perm_test2.tmp" >nul 2>&1
if exist "dist\.perm_test2.tmp" goto :perm_fail

echo [4/5] Building executable with PyInstaller...
echo This may take several minutes...
echo.

pyinstaller ^
    --name="BAB-PrintHub-v1.4.2" ^
    --onefile ^
    --windowed ^
    --icon="%LOGO_PATH%" ^
    --add-data="%LOGO_PATH%;." ^
    --workpath "%WORK_DIR%" ^
    --distpath "%DIST_DIR%" ^
    --specpath "%SPEC_DIR%" ^
    --hidden-import=clr ^
    --hidden-import=pythonnet ^
    --hidden-import=pystray ^
    --hidden-import=PIL ^
    --hidden-import=serial ^
    --hidden-import=cryptography ^
    --hidden-import=requests ^
    --hidden-import=psutil ^
    --hidden-import=xmltodict ^
    --collect-all=pythonnet ^
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
if exist "%DIST_DIR%\\BAB-PrintHub-v1.4.2.exe" (
    if not exist "dist" mkdir dist
    if exist "dist\BAB-PrintHub-v1.4.2.exe" del /F /Q "dist\BAB-PrintHub-v1.4.2.exe" >nul 2>&1
    copy /Y "%DIST_DIR%\\BAB-PrintHub-v1.4.2.exe" dist\BAB-PrintHub-v1.4.2.exe >nul
    if errorlevel 1 (
        echo ERROR: Could not overwrite dist\BAB-PrintHub-v1.4.2.exe. Close any running instance and retry.
        exit /b 1
    )
    echo Executable created: dist\BAB-PrintHub-v1.4.2.exe
    echo Size:
    dir "dist\BAB-PrintHub-v1.4.2.exe" | findstr "BAB-PrintHub"
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
exit /b 0

:perm_fail
echo.
echo ERROR: The current user cannot rename/delete files in build or dist.
echo PyInstaller requires delete/rename permissions for temporary files.
echo.
echo Run this once from an elevated CMD, then re-run build.bat:
echo   icacls "%ROOT_DIR%build" /grant "%USERDOMAIN%\%USERNAME%":(OI)(CI)F /T
echo   icacls "%ROOT_DIR%dist" /grant "%USERDOMAIN%\%USERNAME%":(OI)(CI)F /T
echo.
pause
exit /b 1
