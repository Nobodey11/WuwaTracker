@echo off
REM First run creates a virtual environment and installs dependencies.
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment...
    py -3 -m venv .venv || python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
REM New dependencies after an update (e.g. openpyxl for the Excel export)
python -c "import openpyxl" 2>nul || pip install -r requirements.txt
REM Optional built-in browser for Prydwen guides (about 120 MB, installed once)
python -c "import PySide6.QtWebEngineWidgets" 2>nul || (
    echo Installing the built-in browser for Prydwen guides - one time, about 120 MB...
    pip install -r requirements-web.txt || echo Optional browser not installed - guides will open in your normal browser.
)
start "" pythonw -m wuwa_tracker.app %*
