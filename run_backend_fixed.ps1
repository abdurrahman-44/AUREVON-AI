$ErrorActionPreference = 'Stop'

$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
Set-Location $WorkspaceRoot

$VenvPython = Join-Path $WorkspaceRoot 'backend\.venv\Scripts\python.exe'

Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '        AUREVON AI - Backend Server      ' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host 'ERROR: Backend virtual environment not found.' -ForegroundColor Red
    Write-Host "Expected: $VenvPython" -ForegroundColor Yellow
    Write-Host 'Create it and install backend requirements before starting AUREVON.' -ForegroundColor Yellow
    exit 1
}

$env:PYTHONPATH = $WorkspaceRoot
Write-Host 'Starting FastAPI backend at http://127.0.0.1:8000 ...' -ForegroundColor Green
& $VenvPython -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

if ($LASTEXITCODE -ne 0) {
    Write-Host "Backend stopped with exit code $LASTEXITCODE" -ForegroundColor Red
}
