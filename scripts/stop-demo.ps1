Write-Host "Stopping React/Vite..." -ForegroundColor Cyan
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
foreach ($proc in $nodeProcesses) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

Write-Host "Stopping FastAPI..." -ForegroundColor Cyan
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue
foreach ($proc in $pythonProcesses) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

Write-Host "Stopping Fabric Gateway (WSL node processes)..." -ForegroundColor Cyan
wsl -e pkill -f "node"

Write-Host "Stopping Fabric Containers..." -ForegroundColor Cyan
$chaincodes = docker ps -q --filter "name=dev-peer.*trustledger"
if ($chaincodes) {
    docker stop $chaincodes
}

$fabricNodes = @("orderer.example.com", "peer0.org1.example.com", "peer0.org2.example.com")
foreach ($node in $fabricNodes) {
    $nodeStatus = docker inspect -f '{{.State.Status}}' $node 2>$null
    if ($nodeStatus -eq 'running') {
        Write-Host "Stopping $node..."
        docker stop $node
    }
}

Write-Host "Leaving PostgreSQL running." -ForegroundColor Yellow

Write-Host "==========================================" -ForegroundColor Green
Write-Host "  DPI TRUST FRAMEWORK - STOPPED" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
