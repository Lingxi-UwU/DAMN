@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -X utf8 -c "import sys; assert sys.version_info >= (3,11)"
if errorlevel 1 (
  echo Please install Python 3.11 or newer and add it to PATH.
  pause
  exit /b 1
)
python -X utf8 configure_platform.py
pause
