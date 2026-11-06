# AUREVON AI — Backend Development Server Launcher
$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "      AUREVON AI — Backend Server        " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$WorkspaceRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $WorkspaceRoot

$VenvPython = Join-Path $WorkspaceRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtual environment not found. Please run setup first." -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $WorkspaceRoot
Write-Host "Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Green
& $VenvPython -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
