@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>nul
if errorlevel 1 (
  echo Git was not found. Install Git for Windows and reopen this window.
  pause
  exit /b 1
)
git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 exit /b 1
git remote get-url origin >nul 2>nul
if errorlevel 1 (
  echo No origin remote is configured. Follow docs/DEVELOPMENT.md.
  pause
  exit /b 1
)
git symbolic-ref --quiet HEAD >nul 2>nul
if errorlevel 1 (
  echo Check out a branch before pushing.
  pause
  exit /b 1
)
echo This pushes existing commits on the current branch to origin.
echo It does not stage files, create commits, change remotes, or force-push.
git push origin HEAD
set "PUSH_EXIT=%ERRORLEVEL%"
if not "%PUSH_EXIT%"=="0" echo Push failed. Review the Git error above.
pause
exit /b %PUSH_EXIT%
