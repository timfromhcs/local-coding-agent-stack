<#
.SYNOPSIS
hcscoder-v2 - Autonomous Local Coding Assistant CLI
#>
$ErrorActionPreference = "Continue"

$StackDir = "E:\AI"
$BunExe = "C:\Users\hcsme\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.22_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v22.23.1-win-x64\node_modules\bun\bin\bun.exe"
if (-not (Test-Path $BunExe)) {
    $found = (Get-Command bun.exe -ErrorAction SilentlyContinue)
    if ($found) { $BunExe = $found.Source }
}
$CliBundle = Join-Path $StackDir "claude-code-full\dist\cli.mjs"

$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:4000"
$env:ANTHROPIC_API_KEY = "local-key"
$env:ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
$env:ANTHROPIC_SMALL_FAST_MODEL = "claude-3-5-sonnet-20241022"

# 1. Check & start llama-server (port 8080)
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

# 2. Check & start Proxy (port 4000)
$proxyOk = $false
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:4000/health" -TimeoutSec 2
    if ($resp.status -eq "ok") { $proxyOk = $true }
} catch {}

if (-not $proxyOk) {
    Write-Host "[*] Starting Anthropic translation proxy on port 4000..." -ForegroundColor Cyan
    Start-Process -FilePath "python" -ArgumentList @("-u", "-m", "src.proxy.server", "127.0.0.1", "4000") -WorkingDirectory $StackDir -WindowStyle Hidden
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:4000/health" -TimeoutSec 2
            if ($resp.status -eq "ok") { $proxyOk = $true; break }
        } catch {}
    }
}

if ($args -contains "--gui" -or $args -contains "gui") {
    Write-Host "[+] Opening HCS Coder Web GUI at http://127.0.0.1:4000/gui ..." -ForegroundColor Green
    Start-Process "http://127.0.0.1:4000/gui"
    exit 0
}

# 3. Launch HCS Coder CLI in current directory
& "$BunExe" "$CliBundle" @args
exit $LASTEXITCODE
