# Runs backend pytest suite and frontend production typecheck & build
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$pytestExe = Join-Path $projectRoot "backend\.venv\Scripts\pytest.exe"

Write-Host "=== 1. Running Backend Tests (pytest) ===" -ForegroundColor Cyan
Set-Location -Path (Join-Path $projectRoot "backend")
& $pytestExe -o pythonpath=. tests

if ($LASTEXITCODE -ne 0) {
    Write-Host "Backend tests failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n=== 2. Running Frontend Build & Typecheck ===" -ForegroundColor Cyan
Set-Location -Path (Join-Path $projectRoot "frontend")
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend build failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[SUCCESS] All backend tests and frontend builds passed!" -ForegroundColor Green
