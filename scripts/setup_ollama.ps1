# AUREVON AI — Ollama Model Setup Helper
$ErrorActionPreference = "SilentlyContinue"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "      AUREVON AI — Ollama Setup          " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$OllamaPortTest = Test-NetConnection -ComputerName 127.0.0.1 -Port 11434

if ($OllamaPortTest.TcpTestSucceeded) {
    Write-Host "[OK] Ollama is currently running on http://127.0.0.1:11434" -ForegroundColor Green
    Write-Host "Checking / pulling recommended model 'qwen2.5:3b'..." -ForegroundColor Cyan
    ollama run qwen2.5:3b "Hello, confirm readiness."
} else {
    Write-Host "[!] Ollama is not detected on port 11434." -ForegroundColor Yellow
    Write-Host "To install or start Ollama:" -ForegroundColor White
    Write-Host "  1. If installed, launch the 'Ollama' app from Windows Start Menu." -ForegroundColor White
    Write-Host "  2. If not installed, run: winget install Ollama.Ollama" -ForegroundColor White
    Write-Host "  3. Pull model: ollama run qwen2.5:3b" -ForegroundColor White
}
