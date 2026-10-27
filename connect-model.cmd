@echo off
cd /d "%~dp0"
title Garmin Coach - New Plus sign-in
echo Authorize this separate Garmin Coach account in your browser.
echo Do not send your password or login code in chat.
echo Open the verification page and enter the code shown below.
echo Keep this window open until it confirms that the login has been saved.
echo {"state":"running","exit_code":null}> "%~dp0.private\model-login-status.json"
call "%~dp0openclaw.cmd" models auth login --provider openai --method device-code --profile-id openai:garmin-plus
set "GARMIN_LOGIN_EXIT=%ERRORLEVEL%"
echo {"state":"finished","exit_code": %GARMIN_LOGIN_EXIT%}> "%~dp0.private\model-login-status.json"
echo Login command exit code: %GARMIN_LOGIN_EXIT%
echo.
echo Login process finished. Keep this window open if an error is displayed.
pause
