@echo off
REM Builds dist\WuwaTracker\WuwaTracker.exe (no Python needed on the target PC).
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --windowed --name WuwaTracker --collect-submodules wuwa_tracker --add-data "wuwa_tracker\data\game_data.json;wuwa_tracker\data" launcher.py
echo.
echo Done: dist\WuwaTracker\WuwaTracker.exe
pause
