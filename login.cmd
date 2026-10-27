@echo off
chcp 65001 >nul
title Garmin China updated login
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please follow README.md to prepare Python first.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -X utf8 collect.py --login --portal --days 1
pause
