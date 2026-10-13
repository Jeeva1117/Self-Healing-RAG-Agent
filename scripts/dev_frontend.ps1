# Starts Vite React frontend development server
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Write-Host "Starting Self-Healing RAG Frontend on http://localhost:5173..." -ForegroundColor Cyan
Set-Location -Path (Join-Path $projectRoot "frontend")
npm run dev
