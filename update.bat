@echo off
REM Update code + game data (requires the project to be a git clone), then run the tests.
cd /d "%~dp0"
git pull || (echo git pull failed - is this folder a git clone? & pause & exit /b 1)
if not exist .venv ( py -3 -m venv .venv || python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt pytest
python tools\new_patch.py check
python -m pytest -q tests
pause
