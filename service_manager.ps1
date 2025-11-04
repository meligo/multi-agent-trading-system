# =========================================
#   Multi-Agent Trading System
#   Service Manager for Windows (PowerShell)
# =========================================

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Command,

    [Parameter(Position=1)]
    [ValidateSet('all', 'datahub', 'websocket', 'databento', 'scalper', 'dashboard')]
    [string]$Service = 'all'
)

# Configuration
$LogsDir = "logs"
$PidsDir = "pids"
$DashboardPort = 8505

# Service definitions
$Services = @{
    'datahub' = @{
        Command = "python"
        Args = @("start_datahub_server.py")
        LogFile = "$LogsDir\datahub.log"
        Description = "DataHub Server"
    }
    'websocket' = @{
        Command = "python"
        Args = @("-u", "websocket_collector_modern.py")
        LogFile = "$LogsDir\websocket.log"
        Description = "WebSocket Collector"
    }
    'databento' = @{
        Command = "python"
        Args = @("-u", "start_databento_client.py")
        LogFile = "$LogsDir\databento.log"
        Description = "DataBento Client"
    }
    'scalper' = @{
        Command = "python"
        Args = @("scalping_cli.py", "--run")
        LogFile = "$LogsDir\scalping_engine.log"
        Description = "Scalping Engine"
    }
    'dashboard' = @{
        Command = "streamlit"
        Args = @("run", "dashboard_v2.py", "--server.port", "$DashboardPort")
        LogFile = "$LogsDir\dashboard.log"
        Description = "Dashboard"
    }
}

# Create directories
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}
if (-not (Test-Path $PidsDir)) {
    New-Item -ItemType Directory -Path $PidsDir | Out-Null
}

# Function to start a service
function Start-TradingService {
    param([string]$ServiceName)

    $svc = $Services[$ServiceName]
    Write-Host "🚀 Starting $($svc.Description)..." -ForegroundColor Blue

    try {
        # Start process in background
        $process = Start-Process -FilePath $svc.Command `
            -ArgumentList $svc.Args `
            -RedirectStandardOutput $svc.LogFile `
            -RedirectStandardError "$($svc.LogFile).error" `
            -WindowStyle Hidden `
            -PassThru

        # Save PID
        $process.Id | Out-File "$PidsDir\$ServiceName.pid"

        Write-Host "✅ $($svc.Description) started (PID: $($process.Id))" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ Failed to start $($svc.Description): $_" -ForegroundColor Red
        return $false
    }
}

# Function to stop a service
function Stop-TradingService {
    param([string]$ServiceName)

    $svc = $Services[$ServiceName]
    $pidFile = "$PidsDir\$ServiceName.pid"

    if (Test-Path $pidFile) {
        $pid = Get-Content $pidFile

        try {
            Write-Host "🛑 Stopping $($svc.Description) (PID: $pid)..." -ForegroundColor Blue
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Remove-Item $pidFile -ErrorAction SilentlyContinue
            Write-Host "✅ $($svc.Description) stopped" -ForegroundColor Green
            return $true
        }
        catch {
            Write-Host "⚠️  Could not stop PID $pid" -ForegroundColor Yellow
            return $false
        }
    }
    else {
        Write-Host "⚠️  $($svc.Description) is not running (no PID file)" -ForegroundColor Yellow
        return $false
    }
}

# Function to check service status
function Get-TradingServiceStatus {
    param([string]$ServiceName)

    $svc = $Services[$ServiceName]
    $pidFile = "$PidsDir\$ServiceName.pid"

    if (Test-Path $pidFile) {
        $pid = Get-Content $pidFile

        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue

        if ($process) {
            Write-Host "✅ $($svc.Description): RUNNING (PID: $pid)" -ForegroundColor Green

            # Show CPU and memory
            $cpu = [math]::Round($process.CPU, 2)
            $mem = [math]::Round($process.WorkingSet64 / 1MB, 2)
            Write-Host "   CPU: $cpu s | Memory: $mem MB" -ForegroundColor Gray
        }
        else {
            Write-Host "❌ $($svc.Description): NOT RUNNING (stale PID)" -ForegroundColor Red
            Remove-Item $pidFile -ErrorAction SilentlyContinue
        }
    }
    else {
        Write-Host "⚪ $($svc.Description): NOT RUNNING" -ForegroundColor Gray
    }
}

# Main command logic
Write-Host ""
Write-Host "==========================================" -ForegroundColor Blue
Write-Host "  Multi-Agent Trading System" -ForegroundColor Blue
Write-Host "==========================================" -ForegroundColor Blue
Write-Host ""

switch ($Command) {
    'start' {
        if ($Service -eq 'all') {
            Write-Host "Starting all services..." -ForegroundColor Cyan
            Write-Host ""

            # Start in order with delays
            Start-TradingService 'datahub'
            Start-Sleep -Seconds 3

            Start-TradingService 'websocket'
            Start-Sleep -Seconds 3

            Start-TradingService 'databento'
            Start-Sleep -Seconds 3

            Start-TradingService 'scalper'
            Start-Sleep -Seconds 3

            Start-TradingService 'dashboard'

            Write-Host ""
            Write-Host "🎉 All services started!" -ForegroundColor Green
            Write-Host "Dashboard URL: http://localhost:$DashboardPort" -ForegroundColor Cyan
            Write-Host "Logs directory: $LogsDir" -ForegroundColor Cyan
        }
        else {
            Start-TradingService $Service
        }
    }

    'stop' {
        if ($Service -eq 'all') {
            Write-Host "Stopping all services..." -ForegroundColor Cyan
            Write-Host ""

            # Stop in reverse order
            $serviceOrder = @('dashboard', 'scalper', 'databento', 'websocket', 'datahub')

            foreach ($svcName in $serviceOrder) {
                Stop-TradingService $svcName
            }

            Write-Host ""
            Write-Host "🎉 All services stopped!" -ForegroundColor Green
        }
        else {
            Stop-TradingService $Service
        }
    }

    'restart' {
        Write-Host "Restarting services..." -ForegroundColor Cyan
        Write-Host ""

        if ($Service -eq 'all') {
            # Stop all
            & $PSCommandPath stop all
            Start-Sleep -Seconds 2
            # Start all
            & $PSCommandPath start all
        }
        else {
            Stop-TradingService $Service
            Start-Sleep -Seconds 2
            Start-TradingService $Service
        }
    }

    'status' {
        Write-Host "Service Status:" -ForegroundColor Cyan
        Write-Host ""

        foreach ($svcName in $Services.Keys | Sort-Object) {
            Get-TradingServiceStatus $svcName
        }

        Write-Host ""
        Write-Host "Recent Log Activity:" -ForegroundColor Cyan
        Write-Host ""

        # Show recent log lines
        foreach ($svcName in @('datahub', 'websocket', 'scalper')) {
            $logFile = $Services[$svcName].LogFile

            if (Test-Path $logFile) {
                Write-Host "--- $($Services[$svcName].Description) ---" -ForegroundColor Yellow
                Get-Content $logFile -Tail 3
                Write-Host ""
            }
        }
    }
}

Write-Host ""
