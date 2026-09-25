$ErrorActionPreference = 'Stop'

Write-Host "[1/7] Checking Docker..." -ForegroundColor Cyan
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker CLI is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

Write-Host "[2/7] Starting PostgreSQL..." -ForegroundColor Cyan
$postgresStatus = docker inspect -f '{{.State.Status}}' dpi-postgres 2>$null
if ($postgresStatus -ne 'running') {
    Write-Host "Starting dpi-postgres container..."
    docker start dpi-postgres
} else {
    Write-Host "dpi-postgres is already running."
}

Write-Host "[3/7] Starting Fabric..." -ForegroundColor Cyan
$fabricNodes = @("orderer.example.com", "peer0.org1.example.com", "peer0.org2.example.com")
foreach ($node in $fabricNodes) {
    $nodeStatus = docker inspect -f '{{.State.Status}}' $node 2>$null
    if ($nodeStatus -ne 'running') {
        Write-Host "Starting $node..."
        docker start $node
    } else {
        Write-Host "$node is already running."
    }
}

$chaincodes = docker ps -a --format "{{.Names}}" | Select-String "dev-peer.*trustledger"
if ($chaincodes) {
    foreach ($cc in $chaincodes) {
        $ccStatus = docker inspect -f '{{.State.Status}}' $cc.Line 2>$null
        if ($ccStatus -ne 'running') {
            Write-Host "Starting chaincode container $($cc.Line)..."
            docker start $cc.Line
        }
    }
}

Write-Host "Waiting for Fabric to initialize..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

Write-Host "[4/7] Starting Fabric Gateway..." -ForegroundColor Cyan
$gatewayPort = 8081
$gatewayListening = (Test-NetConnection -ComputerName localhost -Port $gatewayPort -WarningAction SilentlyContinue).TcpTestSucceeded
if ($gatewayListening) {
    Write-Host "Fabric Gateway is already listening on port $gatewayPort."
} else {
    Write-Host "Starting Fabric Gateway in WSL..."
    $gatewayDir = Join-Path $PWD "fabric-gateway"
    # Using wsl directly to launch in a new background window wouldn't preserve the wsl shell nicely as a separate window if we use -WindowStyle Hidden. 
    # We will use Start-Process wsl.exe which pops a new terminal for WSL.
    Start-Process wsl.exe -ArgumentList "--cd", "`"$gatewayDir`"", "-e", "npm", "run", "dev"
}

Write-Host "[5/7] Starting FastAPI..." -ForegroundColor Cyan
$fastapiPort = 8000
$fastapiListening = (Test-NetConnection -ComputerName localhost -Port $fastapiPort -WarningAction SilentlyContinue).TcpTestSucceeded
if ($fastapiListening) {
    Write-Host "FastAPI is already listening on port $fastapiPort."
} else {
    Write-Host "Starting FastAPI backend..."
    $backendDir = Join-Path $PWD "backend"
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd `"$backendDir`"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload"
}

Write-Host "[6/7] Starting React..." -ForegroundColor Cyan
$reactPort = 5173
$reactListening = (Test-NetConnection -ComputerName localhost -Port $reactPort -WarningAction SilentlyContinue).TcpTestSucceeded
if ($reactListening) {
    Write-Host "React is already listening on port $reactPort."
} else {
    Write-Host "Starting React frontend..."
    $frontendDir = Join-Path $PWD "frontend"
    Start-Process cmd.exe -WorkingDirectory $frontendDir -ArgumentList "/k", "npm", "run", "dev"
}

Write-Host "[7/7] Running health checks..." -ForegroundColor Cyan
$servicesReady = $false
$retries = 20
$waitMs = 2000

for ($i = 1; $i -le $retries; $i++) {
    $postgresReady = (Test-NetConnection -ComputerName localhost -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded
    $gatewayReady = (Test-NetConnection -ComputerName localhost -Port 8081 -WarningAction SilentlyContinue).TcpTestSucceeded
    $fastapiReady = (Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue).TcpTestSucceeded
    $reactReady = (Test-NetConnection -ComputerName localhost -Port 5173 -WarningAction SilentlyContinue).TcpTestSucceeded

    if ($postgresReady -and $gatewayReady -and $fastapiReady -and $reactReady) {
        $servicesReady = $true
        break
    }
    Write-Host "Waiting for services to become ready (Attempt $i/$retries)..."
    Start-Sleep -Milliseconds $waitMs
}

if (-not $servicesReady) {
    Write-Host "Error: One or more services failed to start or become ready in time." -ForegroundColor Red
    Write-Host "PostgreSQL: $postgresReady"
    Write-Host "Gateway (8081): $gatewayReady"
    Write-Host "FastAPI (8000): $fastapiReady"
    Write-Host "React (5173): $reactReady"
    exit 1
}

Write-Host "Opening application in browser..."
Start-Process "http://localhost:5173"

Write-Host @"
==========================================
  DPI TRUST FRAMEWORK - READY
==========================================

PostgreSQL       : RUNNING
Fabric           : RUNNING
Fabric Gateway   : RUNNING :8081
FastAPI          : RUNNING :8000
React            : RUNNING :5173

Application:
http://localhost:5173

==========================================
"@ -ForegroundColor Green
