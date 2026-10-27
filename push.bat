@echo off
REM Uploads your commits to GitHub (uses your saved Nobodey11 sign-in).
cd /d "%~dp0"
git push -u origin main --follow-tags
echo.
pause
