@echo off
REM Always uses .venv (Python 3.13) — do not use global Python 3.14 for this project
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run:
  echo   py -3.13 -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist ".env" (
  echo WARNING: No .env in this folder — copy .env.example to .env and set SMTP_USER, SMTP_PASS
)
echo Starting server with .venv Python...
".venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
pause
