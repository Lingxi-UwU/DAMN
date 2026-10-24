@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -X utf8 -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'; import webview"
if errorlevel 1 (
  echo Install Python 3.11+ and run: python -m pip install -r requirements-desktop.txt
  pause
  exit /b 1
)
python -X utf8 desktop.py
if errorlevel 1 pause
