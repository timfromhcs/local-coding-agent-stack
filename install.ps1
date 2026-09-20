<#
.SYNOPSIS
Local Coding Agent Stack — Windows Native PowerShell One-Line Installer
Supports execution from any directory (auto-clones repository if needed).
#>

$ErrorActionPreference = "Stop"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "       Local Coding Agent Stack — Windows Native Installer      " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Ensure Repository Directory
$repoDir = $PWD.Path
if (-not (Test-Path "config/requirements.txt") -or -not (Test-Path "src/proxy/server.py")) {
    $targetDir = Join-Path $PWD.Path "local-coding-agent-stack"
    if (Test-Path (Join-Path $targetDir "config/requirements.txt")) {
        Write-Host "[+] Using existing repository at $targetDir" -ForegroundColor Green
        $repoDir = $targetDir
    } else {
        Write-Host "[+] Repository not detected in current directory." -ForegroundColor Yellow
        Write-Host "[+] Cloning https://github.com/timfromhcs/local-coding-agent-stack.git into $targetDir..." -ForegroundColor Green
        if (Get-Command git -ErrorAction SilentlyContinue) {
            git clone https://github.com/timfromhcs/local-coding-agent-stack.git $targetDir
        } else {
            Write-Host "[!] Git not found. Downloading repository ZIP..." -ForegroundColor Yellow
            $zipUrl = "https://github.com/timfromhcs/local-coding-agent-stack/archive/refs/heads/main.zip"
            $zipPath = Join-Path $env:TEMP "local-coding-agent-stack.zip"
            Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
            Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
            if (Test-Path $targetDir) { Remove-Item $targetDir -Recurse -Force }
            Move-Item (Join-Path $env:TEMP "local-coding-agent-stack-main") $targetDir -Force
            Remove-Item $zipPath -Force
        }
        $repoDir = $targetDir
    }
    Set-Location $repoDir
}

Write-Host "[+] Working directory: $repoDir" -ForegroundColor Green

# 2. Hardware Checks
try {
    $totalRam = (Get-CimInstance Win32_PhysicalMemory -ErrorAction SilentlyContinue | Measure-Object -Property Capacity -Sum).Sum / 1GB
    Write-Host "[+] Detected RAM: $([math]::Round($totalRam, 1)) GB" -ForegroundColor Green
} catch {
    Write-Host "[!] Could not query Win32_PhysicalMemory." -ForegroundColor Yellow
}

# 3. Python Verification
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python 3 is required. Please install Python >= 3.11 from https://www.python.org/ or winget install Python.Python.3.12"
}
$pyVer = python --version
Write-Host "[+] Python version: $pyVer" -ForegroundColor Green

# 4. Bun Verification & Installation
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    $bunBin = Join-Path $env:USERPROFILE ".bun\bin\bun.exe"
    if (Test-Path $bunBin) {
        $env:PATH = "$env:USERPROFILE\.bun\bin;$env:PATH"
    } else {
        Write-Host "[!] Bun not found in PATH. Installing Bun..." -ForegroundColor Yellow
        powershell -c "irm bun.sh/install.ps1 | iex"
        $env:PATH = "$env:USERPROFILE\.bun\bin;$env:PATH"
    }
}
Write-Host "[+] Bun version: $(bun --version)" -ForegroundColor Green

# 5. Python Dependencies
Write-Host "[+] Installing Python requirements from config/requirements.txt..." -ForegroundColor Green
python -m pip install --upgrade pip
python -m pip install -r config/requirements.txt

# 6. Inference Binaries (llama.cpp with Vulkan)
$vulkanServer = Join-Path $repoDir "bin\llama-vulkan\llama-server.exe"
if (-not (Test-Path $vulkanServer) -and -not (Get-Command llama-server -ErrorAction SilentlyContinue)) {
    Write-Host "[+] Downloading prebuilt llama.cpp Vulkan release for Windows..." -ForegroundColor Green
    $binDir = Join-Path $repoDir "bin\llama-vulkan"
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
    $llamaZip = Join-Path $env:TEMP "llama-vulkan-win.zip"
    $llamaUrl = "https://github.com/ggerganov/llama.cpp/releases/download/b4923/llama-b4923-bin-win-vulkan-x64.zip"
    try {
        Invoke-WebRequest -Uri $llamaUrl -OutFile $llamaZip
        Expand-Archive -Path $llamaZip -DestinationPath $binDir -Force
        Remove-Item $llamaZip -Force
        Write-Host "[+] Extracted llama.cpp Vulkan binaries to $binDir" -ForegroundColor Green
    } catch {
        Write-Host "[!] Prebuilt download skipped: $_. You can build or place llama-server in bin/llama-vulkan manually." -ForegroundColor Yellow
    }
} else {
    Write-Host "[+] Verified llama-server binary." -ForegroundColor Green
}

# 7. Model Weights (NeoHorse-1-4B GGUF)
$modelDir = Join-Path $repoDir "models"
New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
$modelFile = Join-Path $modelDir "NeoHorse-1-4B.Q4_K_M.gguf"
if (-not (Test-Path $modelFile)) {
    Write-Host "[+] Downloading NeoHorse-1-4B.Q4_K_M.gguf (2.7 GB) from HuggingFace..." -ForegroundColor Green
    $modelUrl = "https://huggingface.co/mradermacher/NeoHorse-1-4B-GGUF/resolve/main/NeoHorse-1-4B.Q4_K_M.gguf"
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        curl.exe -L -o $modelFile $modelUrl
    } else {
        Invoke-WebRequest -Uri $modelUrl -OutFile $modelFile
    }
    Write-Host "[+] Model downloaded successfully to $modelFile" -ForegroundColor Green
} else {
    $modelSizeMB = [math]::Round((Get-Item $modelFile).Length / 1MB, 1)
    Write-Host "[+] Verified model weights: $modelFile ($modelSizeMB MB)" -ForegroundColor Green
}

# 8. Claude Code CLI Bundle
Write-Host "[+] Checking Claude Code bundle..." -ForegroundColor Green
$cliBundle = Join-Path $repoDir "claude-code-full\dist\cli.mjs"
if (-not (Test-Path $cliBundle)) {
    if (Test-Path (Join-Path $repoDir "claude-code-full")) {
        Write-Host "[+] Building Claude Code CLI bundle via Bun..." -ForegroundColor Green
        Push-Location (Join-Path $repoDir "claude-code-full")
        bun scripts/build-bundle.ts
        Pop-Location
    }
}
Write-Host "[+] Claude Code bundle is ready." -ForegroundColor Green

# 9. Configure Anthropic Client Settings
Write-Host "[+] Configuring Claude Code local settings..." -ForegroundColor Green
$claudeDir = Join-Path $env:USERPROFILE ".claude"
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
$settings | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $claudeDir "settings.json") -Encoding UTF8

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "       Installation Complete! Stack is ready to run.            " -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the stack, open a terminal in $repoDir and run:" -ForegroundColor White
Write-Host "  1. Start Inference Server:  python scripts\run_llama_server.py" -ForegroundColor Yellow
Write-Host "  2. Start API Proxy:         python -m src.proxy.server" -ForegroundColor Yellow
Write-Host "  3. Start RSI Daemon:        python -m src.rsi.daemon loop" -ForegroundColor Yellow
Write-Host "  4. Run Claude Code Agent:   bun claude-code-full\dist\cli.mjs" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
