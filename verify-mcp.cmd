@echo off
chcp 65001 >nul
title Garmin China updated login
cd /d "%~dp0"
echo 原项目的旧认证依赖已失效，正在改用新版中国区只读登录验证。
call "%~dp0login.cmd"
