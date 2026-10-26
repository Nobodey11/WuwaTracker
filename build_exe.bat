@echo off
REM Builds dist\WuwaTracker\WuwaTracker.exe (no Python needed on the target PC).
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -r requirements-web.txt pyinstaller
pyinstaller --noconfirm --windowed --name WuwaTracker --icon wuwa_tracker\assets\icon.ico --collect-submodules wuwa_tracker --add-data "wuwa_tracker\data\game_data.json;wuwa_tracker\data" --add-data "wuwa_tracker\assets;wuwa_tracker\assets" launcher.py
echo.
echo Done: dist\WuwaTracker\WuwaTracker.exe
pause
