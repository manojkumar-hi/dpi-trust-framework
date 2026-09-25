$ErrorActionPreference = 'Stop'

function Test-Port {
    param([int]$Port)
    return (Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded
}

function Start-Postgres {
    Write-Host "[1/6] Checking PostgreSQL..." -ForegroundColor Cyan
    $status = docker inspect -f '{{.State.Status}}' dpi-postgres 2>$null
    if ($status -ne 'running') {
        Write-Host "Starting dpi-postgres container..."
        docker start dpi-postgres
    } else {
        Write-Host "dpi-postgres is already running."
    }
}

function Start-Fabric {
    Write-Host "[2/6] Starting Fabric Containers..." -ForegroundColor Cyan
    $nodes = @("orderer.example.com", "peer0.org1.example.com", "peer0.org2.example.com")
    foreach ($node in $nodes) {
        $status = docker inspect -f '{{.State.Status}}' $node 2>$null
        if ($status -ne 'running') {
            Write-Host "Starting $node..."
            docker start $node
        } else {
            Write-Host "$node is already running."
        }
    }

    $chaincodes = docker ps -a --format "{{.Names}}" | Select-String "dev-peer.*trustledger"
    if ($chaincodes) {
        foreach ($cc in $chaincodes) {
            $ccName = $cc.Line
            $ccStatus = docker inspect -f '{{.State.Status}}' $ccName 2>$null
            if ($ccStatus -ne 'running') {
                Write-Host "Starting chaincode container $ccName..."
                docker start $ccName
            }
        }
    }
}

function Wait-ForFabric {
    Write-Host "Waiting for Fabric to initialize..." -ForegroundColor Cyan
    Start-Sleep -Seconds 5
}

function Start-FabricGateway {
    Write-Host "[3/6] Starting Fabric Gateway..." -ForegroundColor Cyan
    if (Test-Port -Port 8081) {
        Write-Host "Fabric Gateway is already listening on port 8081."
    } else {
        Write-Host "Starting Fabric Gateway in WSL..."
        $gatewayDir = Join-Path $PWD "fabric-gateway"
        Start-Process wsl.exe -ArgumentList "--cd", "`"$gatewayDir`"", "-e", "npm", "run", "dev"
    }
}

function Start-Backend {
    Write-Host "[4/6] Starting FastAPI..." -ForegroundColor Cyan
    if (Test-Port -Port 8000) {
        Write-Host "FastAPI is already listening on port 8000."
    } else {
        Write-Host "Starting FastAPI backend..."
        $backendDir = Join-Path $PWD "backend"
        Start-Process cmd.exe -WorkingDirectory $backendDir -ArgumentList "/k", ".venv\Scripts\activate.bat", "&&", "uvicorn", "app.main:app", "--reload"
    }
}

function Start-Frontend {
    Write-Host "[5/6] Starting React/Vite..." -ForegroundColor Cyan
    if (Test-Port -Port 5173) {
        Write-Host "React is already listening on port 5173."
    } else {
        Write-Host "Starting React frontend..."
        $frontendDir = Join-Path $PWD "frontend"
        # Using cmd.exe with /k to launch in a new persistent CMD window reliably
        Start-Process cmd.exe -WorkingDirectory $frontendDir -ArgumentList "/k", "npm", "run", "dev"
    }
}

function Test-ProjectHealth {
    Write-Host "[6/6] Verifying Project Health..." -ForegroundColor Cyan
    $retries = 20
    $waitMs = 2000
    $servicesReady = $false

    for ($i = 1; $i -le $retries; $i++) {
        $postgresReady = Test-Port -Port 5432
        $gatewayReady = Test-Port -Port 8081
        $fastapiReady = Test-Port -Port 8000
        $reactReady = Test-Port -Port 5173

        if ($postgresReady -and $gatewayReady -and $fastapiReady -and $reactReady) {
            $servicesReady = $true
            break
        }
        Write-Host "Waiting for all services to become ready (Attempt $i/$retries)..."
        Start-Sleep -Milliseconds $waitMs
    }

    if (-not $servicesReady) {
        Write-Host "Error: One or more services failed to become ready in time." -ForegroundColor Red
        Write-Host "PostgreSQL (5432) : $postgresReady"
        Write-Host "Gateway    (8081) : $gatewayReady"
        Write-Host "FastAPI    (8000) : $fastapiReady"
        Write-Host "React      (5173) : $reactReady"
        exit 1
    }
}

function Open-Application {
    Write-Host "Opening application in browser..."
    Start-Process "http://localhost:5173"
    
    Write-Host @"
==============================================
    DPI TRUST FRAMEWORK - PROJECT READY
==============================================

PostgreSQL       : READY
Hyperledger      : READY
Fabric Gateway   : READY :8081
FastAPI          : READY :8000
React            : READY :5173

Application:
http://localhost:5173

==============================================
"@ -ForegroundColor Green
}

# Main Execution Flow
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker CLI is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

Start-Postgres
Start-Fabric
Wait-ForFabric
Start-FabricGateway
Start-Backend
Start-Frontend
Test-ProjectHealth
Open-Application
