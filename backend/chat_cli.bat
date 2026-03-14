@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run: py -3.13 -m venv .venv ^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "%~dp0chat_cli.py" %*
