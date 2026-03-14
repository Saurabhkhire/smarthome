# Always uses .venv — avoids Python 3.14 global (missing langchain_openai)
Set-Location $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Create venv first: py -3.13 -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}
& ".\.venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
