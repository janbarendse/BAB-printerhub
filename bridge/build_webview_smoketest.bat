@echo off
REM Quick Nuitka build for the minimal webview smoketest
REM Uses Python 3.13 and prefers Edge/WebView2 backend (pywebview edgechromium)

setlocal
cd /d "%~dp0"

echo [1/4] Checking Python 3.13...
py -3.13 --version || goto :error

echo [2/4] Building webview_smoketest.exe with Nuitka...
py -3.13 -m nuitka ^
    --onefile ^
    --windows-console-mode=force ^
    --disable-ccache ^
    --output-dir=dist-smoketest ^
    --include-module=clr ^
    --include-module=pythonnet ^
    webview_smoketest.py
if errorlevel 1 goto :error

echo [3/4] Copying log/readme hints...
if not exist "dist-smoketest" mkdir dist-smoketest
copy /Y webview_smoketest.py dist-smoketest\webview_smoketest_source.py >nul

echo [4/4] Done. Run from dist-smoketest\webview_smoketest.exe
goto :eof

:error
echo Build failed (%errorlevel%)
exit /b %errorlevel%
