param(
    [ValidateSet("start", "restart", "stop")]
    [string]$Action = "start",

    [int]$Port = 8088,

    [string]$HostName = "127.0.0.1",

    [string]$DatabasePath = "",

    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $RootDir "mis_mvp"
$DataDir = Join-Path $AppDir "data"
$RuntimeDir = Join-Path ([System.IO.Path]::GetTempPath()) "MuchenMIS"
$LogDir = Join-Path $RuntimeDir "logs"

if (-not $DatabasePath) {
    $DatabasePath = Join-Path $DataDir "mis_mvp.sqlite3"
}

function Ensure-RuntimeDirs {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Python\bin\python.exe"),
        "python",
        "py"
    )
    foreach ($candidate in $candidates) {
        try {
            $cmd = Get-Command $candidate -ErrorAction Stop
            return $cmd.Source
        } catch {
        }
    }
    throw "Python was not found. Install Python or add python.exe to PATH."
}

function Get-PortPids {
    param([int]$TargetPort)
    $lines = netstat -ano | Select-String -Pattern "LISTENING" | Where-Object {
        $_.Line -match "[:.]$TargetPort\s"
    }
    $pids = @()
    foreach ($line in $lines) {
        $parts = ($line.Line.Trim() -split "\s+")
        if ($parts.Length -ge 5) {
            $pids += [int]$parts[-1]
        }
    }
    $pids | Sort-Object -Unique
}

function Stop-Port {
    param([int]$TargetPort)
    $pids = @(Get-PortPids -TargetPort $TargetPort)
    if ($pids.Count -eq 0) {
        Write-Host "No service is listening on port $TargetPort."
        return
    }
    foreach ($pidValue in $pids) {
        try {
            Stop-Process -Id $pidValue -Force -ErrorAction Stop
            Write-Host "Stopped process PID=$pidValue on port $TargetPort."
        } catch {
            Write-Warning "Failed to stop PID=${pidValue}: $($_.Exception.Message)"
        }
    }
}

function Start-App {
    param(
        [int]$TargetPort,
        [string]$TargetHost
    )
    Ensure-RuntimeDirs
    $existing = @(Get-PortPids -TargetPort $TargetPort)
    if ($existing.Count -gt 0) {
        Write-Host "Port $TargetPort is already running. PID: $($existing -join ', ')"
    } else {
        $python = Find-Python
        $env:MIS_DATABASE_PATH = $DatabasePath
        $logFile = Join-Path $LogDir "mis_mvp_$TargetPort.log"
        $errFile = Join-Path $LogDir "mis_mvp_$TargetPort.err.log"
        Start-Process -FilePath $python `
            -ArgumentList "-B", "-m", "uvicorn", "backend.app:app", "--host", $TargetHost, "--port", "$TargetPort" `
            -WindowStyle Hidden `
            -RedirectStandardOutput $logFile `
            -RedirectStandardError $errFile `
            -WorkingDirectory $AppDir | Out-Null

        Start-Sleep -Seconds 2
        $started = @(Get-PortPids -TargetPort $TargetPort)
        if ($started.Count -eq 0) {
            Write-Host "Service failed to start. Check logs:"
            Write-Host "  $logFile"
            Write-Host "  $errFile"
            exit 1
        }
        Write-Host "Service started: http://$TargetHost`:$TargetPort/"
        Write-Host "Database: $DatabasePath"
        Write-Host "Log: $logFile"
    }

    if (-not $NoBrowser) {
        Start-Process "http://$TargetHost`:$TargetPort/"
    }
}

switch ($Action) {
    "start" {
        Start-App -TargetPort $Port -TargetHost $HostName
    }
    "restart" {
        Stop-Port -TargetPort $Port
        Start-Sleep -Seconds 1
        Start-App -TargetPort $Port -TargetHost $HostName
    }
    "stop" {
        Stop-Port -TargetPort $Port
    }
}
