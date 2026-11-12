$ErrorActionPreference = 'Stop'

$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $WorkspaceRoot 'frontend'

Write-Host '=========================================' -ForegroundColor Cyan
Write-Host '        AUREVON AI - Frontend Server     ' -ForegroundColor Cyan
Write-Host '=========================================' -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $FrontendRoot)) {
    Write-Host 'ERROR: Frontend folder not found.' -ForegroundColor Red
    Write-Host "Expected: $FrontendRoot" -ForegroundColor Yellow
    exit 1
}

$Node = Get-Command node -ErrorAction SilentlyContinue
$Npm = Get-Command npm -ErrorAction SilentlyContinue

if (-not $Node -or -not $Npm) {
    Write-Host 'ERROR: Node.js and npm must be installed and available in PATH.' -ForegroundColor Red
    exit 1
}

$NodeModules = Join-Path $FrontendRoot 'node_modules'
$PackageJson = Join-Path $FrontendRoot 'package.json'

if (-not (Test-Path -LiteralPath $PackageJson)) {
    Write-Host 'ERROR: frontend package.json was not found.' -ForegroundColor Red
    exit 1
}

Set-Location $FrontendRoot

if (-not (Test-Path -LiteralPath $NodeModules)) {
    Write-Host 'Frontend dependencies are missing. Installing with npm install...' -ForegroundColor Yellow
    & npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: npm install failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host 'Starting React frontend at http://127.0.0.1:5173 ...' -ForegroundColor Green
& npm run dev -- --host 127.0.0.1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend stopped with exit code $LASTEXITCODE" -ForegroundColor Red
}