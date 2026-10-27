@echo off
chcp 65001 >nul
title Garmin Coach - WeChat QR login
cd /d "%~dp0"
call "%~dp0openclaw.cmd" channels login --channel openclaw-weixin
echo.
pause
