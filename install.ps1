<#
.SYNOPSIS
Local Coding Agent Stack — Windows Native PowerShell Installer
#>

$ErrorActionPreference = "Stop"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "       Local Coding Agent Stack — Windows Native Installer      " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Hardware Check
$totalRam = (Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum / 1GB
Write-Host "[+] Detected RAM: $([math]::Round($totalRam, 1)) GB" -ForegroundColor Green

# 2. Python Check
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed. Please install Python 3.11+."
}
Write-Host "[+] Python version: $(python --version)" -ForegroundColor Green

# 3. Bun Check
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Bun not found in PATH. Installing Bun..." -ForegroundColor Yellow
    powershell -c "irm bun.sh/install.ps1 | iex"
    $env:PATH = "$env:USERPROFILE\.bun\bin;$env:PATH"
}
Write-Host "[+] Bun version: $(bun --version)" -ForegroundColor Green

# 4. Python Dependencies
Write-Host "[+] Installing Python requirements..." -ForegroundColor Green
pip install -r config/requirements.txt

# 5. Build Claude Code CLI bundle
Write-Host "[+] Building Claude Code bundle..." -ForegroundColor Green
if (Test-Path "claude-code-full") {
    Push-Location claude-code-full
    bun scripts/build-bundle.ts
    Pop-Location
}

# 6. Configure Claude Settings
Write-Host "[+] Configuring Claude Code local settings..." -ForegroundColor Green
$claudeDir = "$env:USERPROFILE\.claude"
if (-not (Test-Path $claudeDir)) {
    New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null
}

$settings = @{
    env = @{
        ANTHROPIC_BASE_URL = "http://127.0.0.1:4000"
        ANTHROPIC_AUTH_TOKEN = "local-key"
        ANTHROPIC_MODEL = "auto"
        ANTHROPIC_DEFAULT_SONNET_MODEL = "auto"
        ANTHROPIC_DEFAULT_HAIKU_MODEL = "auto"
    }
}
$settings | ConvertTo-Json -Depth 5 | Set-Content "$claudeDir\settings.json" -Encoding UTF8

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Installation Complete! To start the stack, run:" -ForegroundColor Green
Write-Host "  python scripts\run_llama_server.py" -ForegroundColor Yellow
Write-Host "  python -m src.proxy.server" -ForegroundColor Yellow
Write-Host "  bun claude-code-full\dist\cli.mjs" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
