@echo off
chcp 65001 >nul
title Garmin MCP verification
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please follow docs/SETUP.md to prepare Python first.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -X utf8 verify_current_mcp.py %*
set "VERIFY_EXIT=%ERRORLEVEL%"
pause
exit /b %VERIFY_EXIT%
