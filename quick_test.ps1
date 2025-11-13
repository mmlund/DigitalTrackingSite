# Quick test script - tests if server is running and runs tests
Write-Host "Checking if Flask server is running..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/" -TimeoutSec 2 -UseBasicParsing
    Write-Host "✅ Server is running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Running tests..." -ForegroundColor Cyan
    & "$PSScriptRoot\venv\Scripts\python.exe" "$PSScriptRoot\test_track_endpoint.py"
} catch {
    Write-Host "❌ Server is NOT running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the server first:" -ForegroundColor Yellow
    Write-Host "  1. Open a NEW terminal window" -ForegroundColor Yellow
    Write-Host "  2. Run: .\start_server.ps1" -ForegroundColor Yellow
    Write-Host "  3. Then come back and run this script again" -ForegroundColor Yellow
}

