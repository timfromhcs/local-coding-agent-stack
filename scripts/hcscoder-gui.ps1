<#
.SYNOPSIS
hcscoder-gui — Launcher for HCS Coder v2 Web GUI
#>
$ErrorActionPreference = "Continue"
$StackDir = "E:\AI"

# 1. Ensure llama-server is alive
$llamaOk = $false
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -TimeoutSec 2
    if ($resp.status -eq "ok") { $llamaOk = $true }
} catch {}

if (-not $llamaOk) {
    Write-Host "[*] Starting local llama-server (Vulkan GPU)..." -ForegroundColor Cyan
    Start-Process -FilePath "python" -ArgumentList "$StackDir\scripts\run_llama_server.py" -WorkingDirectory $StackDir -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -TimeoutSec 2
            if ($resp.status -eq "ok") { $llamaOk = $true; break }
        } catch {}
    }
}

# 2. Ensure Proxy is alive
$proxyOk = $false
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:4000/health" -TimeoutSec 2
    if ($resp.status -eq "ok") { $proxyOk = $true }
} catch {}

if (-not $proxyOk) {
    Write-Host "[*] Starting Anthropic translation proxy on port 4000..." -ForegroundColor Cyan
    Start-Process -FilePath "python" -ArgumentList "-u -m src.proxy.server 127.0.0.1 4000" -WorkingDirectory $StackDir -WindowStyle Hidden
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:4000/health" -TimeoutSec 2
            if ($resp.status -eq "ok") { $proxyOk = $true; break }
        } catch {}
    }
}

Write-Host "[✓] Stack is live! Opening Web GUI in your default browser..." -ForegroundColor Green
Start-Process "http://127.0.0.1:4000/gui"
