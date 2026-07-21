$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot

Write-Host "Starting RackDCIM Pro development environment..." -ForegroundColor Cyan

# Backend
Set-Location "$RootDir\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -q
Start-Process -NoNewWindow python -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"

# Frontend
Set-Location "$RootDir\frontend"
npm install -q
Start-Process -NoNewWindow npm -ArgumentList "run", "dev"

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/api/v1/docs" -ForegroundColor Green
