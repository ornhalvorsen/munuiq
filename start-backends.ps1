# AnalyticsIQ - Start backend server
# Single backend on port 8000 handles both Claude and Ollama models

Write-Host "Starting AnalyticsIQ backend on port 8000..." -ForegroundColor Cyan

# Check if Ollama is running
try {
    $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2
    Write-Host "  Ollama detected - local models enabled" -ForegroundColor Green
} catch {
    Write-Host "  Ollama not running - local models disabled" -ForegroundColor Yellow
    Write-Host "  To enable: ollama serve" -ForegroundColor Yellow
}

# Start backend
Set-Location "$PSScriptRoot\backend"
python -m uvicorn app.main:app --reload --port 8000
