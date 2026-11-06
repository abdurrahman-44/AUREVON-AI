# AUREVON AI — Full Application Development Launcher
$ErrorActionPreference = "Stop"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "             Starting AUREVON AI                 " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$WorkspaceRoot = (Get-Item $PSScriptRoot).Parent.FullName

# Start backend job in new terminal window or background process
Write-Host "Starting backend server..." -ForegroundColor Green
$BackendProcess = Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy Bypass", "-File `"$WorkspaceRoot\scripts\run_backend.ps1`"" -PassThru

# Start frontend in current or separate process
Write-Host "Starting frontend server..." -ForegroundColor Green
$FrontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy Bypass", "-File `"$WorkspaceRoot\scripts\run_frontend.ps1`"" -PassThru

Write-Host "`nAUREVON AI is launching!" -ForegroundColor Cyan
Write-Host "  • Web Interface: http://127.0.0.1:5173" -ForegroundColor White
Write-Host "  • Backend API:   http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  • API Docs:      http://127.0.0.1:8000/docs" -ForegroundColor White
