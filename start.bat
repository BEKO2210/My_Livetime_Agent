@echo off
REM Startet den Life Agent unter Windows.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 wurde nicht gefunden.
  echo Bitte von https://www.python.org/downloads/ installieren ^(Haken bei "Add to PATH"^).
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Richte die Umgebung ein ^(einmalig^)...
  python -m venv .venv
  .venv\Scripts\python -m pip install --quiet --upgrade pip
  .venv\Scripts\pip install --quiet -r requirements.txt
)

.venv\Scripts\python -m lifeagent %*
pause
