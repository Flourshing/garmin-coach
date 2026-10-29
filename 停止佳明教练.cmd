@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-coach.ps1"
if errorlevel 1 pause
