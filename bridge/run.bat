@echo off
setlocal
cd /d "%~dp0"
py -3.13 -m src.fiscal_printer_hub
