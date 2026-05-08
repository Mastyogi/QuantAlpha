# ============================================================
# QuantAlpha — 24/7 Auto Training Runner (PowerShell)
# Run: powershell -ExecutionPolicy Bypass -File run_training.ps1
# ============================================================

param(
    [switch]$NoRestart,      # Don't auto-restart on crash
    [switch]$Background,     # Run as background job
    [int]$RestartDelaySec = 15
)

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT

$LogDir   = Join-Path $ROOT "logs"
$ModelDir = Join-Path $ROOT "models"
$LogFile  = Join-Path $LogDir ("training_" + (Get-Date -Format "yyyyMMdd") + ".log")

# ── Banner ────────────────────────────────────────────────────────────────────
function Write-Banner {
    $line = "=" * 62
    Write-Host ""
    Write-Host $line -ForegroundColor Cyan
    Write-Host "  QuantAlpha 24/7 Continuous Improvement System" -ForegroundColor Yellow
    Write-Host ("  " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray
    Write-Host $line -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($n, $msg) {
    Write-Host "[$n] $msg" -ForegroundColor Green
}

function Write-Err($msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
}

# ── Pre-flight checks ─────────────────────────────────────────────────────────
Write-Banner

# Python check
try {
    $pyVer = python --version 2>&1
    Write-Step "1/5" "Python found: $pyVer"
} catch {
    Write-Err "Python not found. Install Python 3.10+ and add to PATH."
    exit 1
}

# Create dirs
New-Item -ItemType Directory -Force -Path $LogDir   | Out-Null
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
Write-Step "2/5" "Directories ready: logs/, models/"

# Install dependencies
Write-Step "3/5" "Checking dependencies (pip install -r requirements.txt)..."
$pipLog = Join-Path $LogDir "pip_install.log"
pip install -r requirements.txt -q --no-warn-script-location 2>&1 | Out-File $pipLog
Write-Host "      Done. See $pipLog for details." -ForegroundColor Gray

# Kill stale port 8000
Write-Step "4/5" "Releasing port 8000 if occupied..."
$portProcs = netstat -ano 2>$null | Select-String ":8000 "
foreach ($line in $portProcs) {
    $pid_ = ($line -split '\s+')[-1]
    if ($pid_ -match '^\d+$') {
        Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
    }
}

# Set PYTHONPATH
$env:PYTHONPATH = $ROOT
Write-Step "5/5" "PYTHONPATH = $ROOT"

Write-Host ""
Write-Host "  Log file : $LogFile" -ForegroundColor Gray
Write-Host "  Stop     : Ctrl+C" -ForegroundColor Gray
Write-Host ""

# ── Background mode ───────────────────────────────────────────────────────────
if ($Background) {
    Write-Host "Starting as background job..." -ForegroundColor Yellow
    $job = Start-Job -ScriptBlock {
        param($root, $log)
        Set-Location $root
        $env:PYTHONPATH = $root
        while ($true) {
            python continuous_improvement_system.py 2>&1 | Tee-Object -FilePath $log -Append
            Start-Sleep -Seconds 15
        }
    } -ArgumentList $ROOT, $LogFile
    Write-Host "Job ID: $($job.Id)  |  Use 'Receive-Job $($job.Id)' to see output" -ForegroundColor Cyan
    Write-Host "Stop with: Stop-Job $($job.Id)" -ForegroundColor Cyan
    return
}

# ── Foreground loop with auto-restart ────────────────────────────────────────
$iteration = 0
while ($true) {
    $iteration++
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] Run #$iteration — starting continuous_improvement_system.py" -ForegroundColor Cyan

    # Tee output to both console and log file
    $proc = Start-Process python `
        -ArgumentList "continuous_improvement_system.py" `
        -NoNewWindow `
        -PassThru `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError  (Join-Path $LogDir "training_err.log")

    $proc.WaitForExit()
    $code = $proc.ExitCode

    $ts = Get-Date -Format "HH:mm:ss"
    if ($code -eq 0) {
        Write-Host "[$ts] Exited cleanly (code 0)." -ForegroundColor Green
    } else {
        Write-Host "[$ts] Crashed (code $code). Check logs\training_err.log" -ForegroundColor Red
    }

    if ($NoRestart) {
        Write-Host "NoRestart flag set — exiting." -ForegroundColor Yellow
        break
    }

    Write-Host "  Restarting in ${RestartDelaySec}s... (Ctrl+C to abort)" -ForegroundColor Gray
    Start-Sleep -Seconds $RestartDelaySec
}
