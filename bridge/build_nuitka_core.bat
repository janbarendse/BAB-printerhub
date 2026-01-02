@echo off
REM ============================================================
REM BAB-Cloud PrintHub - Nuitka Core Build Script
REM ============================================================

setlocal
cd /d "%~dp0"

set "APP_VERSION=1.5.2"
set "APP_NAME=BAB-PrintHub-v%APP_VERSION%"
set "BUILD_TAG=%RANDOM%%RANDOM%"
set "MODULE_NAME=fiscal_printer_hub"
set "OUT_DIR=dist-nuitka\\build-%BUILD_TAG%"
set "DIST_DIR=%OUT_DIR%\\%MODULE_NAME%.dist"
set "NUITKA_CACHE_DIR=dist-nuitka\\nuitka-cache"

echo.
echo ============================================================
echo BAB-Cloud PrintHub v%APP_VERSION% - Nuitka Core Build
echo ============================================================
echo.

echo [1/5] Checking Python 3.13...
py -3.13 --version || goto :error

echo [2/5] Checking Nuitka...
py -3.13 -m nuitka --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Nuitka is not installed for Python 3.13.
    echo Install with: py -3.13 -m pip install nuitka
    goto :error
)

echo [3/5] Preparing output folder...
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
if not exist "%NUITKA_CACHE_DIR%" mkdir "%NUITKA_CACHE_DIR%"
echo Using build tag: %BUILD_TAG%

REM Verify we can rename/delete in output folder
set "PERM_TEST=%OUT_DIR%\.perm_test.tmp"
echo test> "%PERM_TEST%" 2>nul
if not exist "%PERM_TEST%" goto :perm_fail
ren "%PERM_TEST%" ".perm_test2.tmp" >nul 2>&1
if errorlevel 1 goto :perm_fail
del /F /Q "%OUT_DIR%\.perm_test2.tmp" >nul 2>&1
if exist "%OUT_DIR%\.perm_test2.tmp" goto :perm_fail

echo [4/5] Building core with Nuitka (standalone)...
py -3.13 -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --enable-plugin=pyside6 ^
    --assume-yes-for-downloads ^
    --disable-ccache ^
    --nofollow-import-to=tkinter,matplotlib,numpy,scipy,pandas,pytest,PyQt5,PyQt6,wx,webview,pywebview ^
    --noinclude-qt-plugins=all ^
    --include-qt-plugins=platforms,styles,iconengines,imageformats ^
    --output-dir="%OUT_DIR%" ^
    --output-filename="%APP_NAME%" ^
    --include-data-file=src\\assets\\icons\\arrow_down.svg=src\\assets\\icons\\arrow_down.svg ^
    --include-data-file=src\\assets\\icons\\arrow_up.svg=src\\assets\\icons\\arrow_up.svg ^
    --include-data-file=src\\assets\\logo.png=src\\assets\\logo.png ^
    --include-module=clr ^
    --include-package=pythonnet ^
    src\fiscal_printer_hub.py
if errorlevel 1 goto :error

echo [5/5] Copying runtime payloads...
if not exist "%DIST_DIR%" (
    echo ERROR: Nuitka output folder not found: %DIST_DIR%
    goto :error
)
if exist "%DIST_DIR%\\%MODULE_NAME%.exe" (
    ren "%DIST_DIR%\\%MODULE_NAME%.exe" "%APP_NAME%.exe" >nul 2>&1
)
copy /Y config.json "%DIST_DIR%\config.json" >nul
copy /Y config.json "%OUT_DIR%\config.json" >nul
if not exist "%DIST_DIR%\\src\\assets\\icons" mkdir "%DIST_DIR%\\src\\assets\\icons"
copy /Y src\\assets\\logo.png "%DIST_DIR%\\src\\assets\\logo.png" >nul
copy /Y src\\assets\\icons\\arrow_down.svg "%DIST_DIR%\\src\\assets\\icons\\arrow_down.svg" >nul
copy /Y src\\assets\\icons\\arrow_up.svg "%DIST_DIR%\\src\\assets\\icons\\arrow_up.svg" >nul
powershell -ExecutionPolicy Bypass -Command "& '%~dp0package_ui_payload.ps1' -OutputDir '%DIST_DIR%' -IncludeRuntime $true"

echo ============================================================
echo Nuitka build completed: %DIST_DIR%\%APP_NAME%.exe
echo ============================================================
echo.
goto :eof

:perm_fail
echo.
echo ERROR: The current user cannot rename/delete files in %OUT_DIR%.
echo Fix with elevated CMD:
echo   icacls "%~dp0%OUT_DIR%" /grant "%USERDOMAIN%\%USERNAME%":(OI)(CI)F /T
echo.
goto :error

:error
echo Build failed.
exit /b 1
