# AUREVON AI — Frontend Development Server Launcher
$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "      AUREVON AI — Frontend Server       " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$WorkspaceRoot = (Get-Item $PSScriptRoot).Parent.FullName
$FrontendDir = Join-Path $WorkspaceRoot "frontend"
Set-Location $FrontendDir

# Find node
$NodeCmd = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $NodeCmd) {
    if (Test-Path "C:\Users\abdur\Downloads\NodeJs\node.exe") {
        $NodeCmd = "C:\Users\abdur\Downloads\NodeJs\node.exe"
    } else {
        Write-Host "Node.js executable could not be found." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Starting Vite React frontend on http://127.0.0.1:5173..." -ForegroundColor Green
& $NodeCmd ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
