# Starts FastAPI backend development server using the virtual environment
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$pythonExe = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"

Write-Host "Starting Self-Healing RAG Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
Set-Location -Path (Join-Path $projectRoot "backend")
& $pythonExe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
