$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$PipIndex = "https://pypi.tuna.tsinghua.edu.cn/simple"

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSec = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

function Ensure-BackendDeps {
    $venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
    $reqFile = Join-Path $BackendDir "requirements.txt"
    $stampFile = Join-Path $BackendDir ".venv\.deps.stamp"

    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating backend virtualenv..." -ForegroundColor Yellow
        python -m venv (Join-Path $BackendDir ".venv")
    }

    $needInstall = $true
    if ((Test-Path $stampFile) -and (Test-Path $reqFile)) {
        $stamp = Get-Content $stampFile -Raw
        $hash = (Get-FileHash $reqFile -Algorithm SHA256).Hash
        if ($stamp.Trim() -eq $hash) {
            & $venvPython -c "import fastapi, uvicorn" 2>$null
            if ($LASTEXITCODE -eq 0) { $needInstall = $false }
        }
    }

    if ($needInstall) {
        Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
        & $venvPython -m pip install --upgrade pip -q -i $PipIndex
        & $venvPython -m pip install -r $reqFile -q -i $PipIndex
        & $venvPython -m pip install pytest pytest-asyncio httpx -q -i $PipIndex
        (Get-FileHash $reqFile -Algorithm SHA256).Hash | Set-Content $stampFile -NoNewline
    } else {
        Write-Host "Backend dependencies up to date." -ForegroundColor DarkGray
    }
}

function Ensure-FrontendDeps {
    $lockFile = Join-Path $FrontendDir "package-lock.json"
    $stampFile = Join-Path $FrontendDir "node_modules\.deps.stamp"
    $needInstall = $true

    if ((Test-Path (Join-Path $FrontendDir "node_modules")) -and (Test-Path $stampFile) -and (Test-Path $lockFile)) {
        $stamp = Get-Content $stampFile -Raw
        $hash = (Get-FileHash $lockFile -Algorithm SHA256).Hash
        if ($stamp.Trim() -eq $hash) { $needInstall = $false }
    }

    if ($needInstall) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
        Push-Location $FrontendDir
        try {
            npm install --silent
        } finally {
            Pop-Location
        }
        if (Test-Path $lockFile) {
            (Get-FileHash $lockFile -Algorithm SHA256).Hash | Set-Content $stampFile -NoNewline
        }
    } else {
        Write-Host "Frontend dependencies up to date." -ForegroundColor DarkGray
    }
}

Write-Host "Starting RackDCIM Pro development environment..." -ForegroundColor Cyan

Ensure-BackendDeps
Ensure-FrontendDeps

$venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (Test-PortListening 8000) {
    Write-Host "Backend already listening on :8000" -ForegroundColor DarkGray
} else {
    Write-Host "Starting backend on :8000 ..." -ForegroundColor Yellow
    Start-Process -WorkingDirectory $BackendDir -FilePath $venvPython `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000" `
        -WindowStyle Hidden
}

if (Test-PortListening 5173) {
    Write-Host "Frontend already listening on :5173" -ForegroundColor DarkGray
} else {
    Write-Host "Starting frontend on :5173 ..." -ForegroundColor Yellow
    $npmCommand = (Get-Command "npm.cmd" -ErrorAction Stop).Source
    Start-Process -WorkingDirectory $FrontendDir -FilePath $npmCommand `
        -ArgumentList "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173" `
        -WindowStyle Hidden
}

$backendOk = Wait-HttpOk "http://127.0.0.1:8000/api/v1/health"
$frontendOk = Wait-HttpOk "http://127.0.0.1:5173/"

Write-Host ""
if ($backendOk) {
    Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
    Write-Host "API Docs: http://localhost:8000/api/v1/docs" -ForegroundColor Green
} else {
    Write-Host "Backend:  failed to become healthy within timeout" -ForegroundColor Red
}
if ($frontendOk) {
    Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
} else {
    Write-Host "Frontend: failed to become ready within timeout" -ForegroundColor Red
}
