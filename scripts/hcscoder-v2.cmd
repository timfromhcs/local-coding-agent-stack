@echo off
setlocal enabledelayedexpansion

set "STACK_DIR=E:\AI"
set "BUN_EXE=C:\Users\hcsme\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.22_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v22.23.1-win-x64\node_modules\bun\bin\bun.exe"
if not exist "%BUN_EXE%" (
    for /f "tokens=*" %%i in ('where bun.exe 2^>nul') do set "BUN_EXE=%%i"
)
set "CLI_BUNDLE=%STACK_DIR%\claude-code-full\dist\cli.mjs"

REM  Environment variables for local stack
set "ANTHROPIC_BASE_URL=http://127.0.0.1:4000"
set "ANTHROPIC_API_KEY=local-key"
set "ANTHROPIC_MODEL=claude-3-5-sonnet-20241022"
set "ANTHROPIC_SMALL_FAST_MODEL=claude-3-5-sonnet-20241022"

REM  Check if llama-server (8080) is running
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo [*] Starting llama-server on port 8080...
    start /B "" python "%STACK_DIR%\scripts\run_llama_server.py"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } } catch { Start-Sleep -Seconds 1 } }; exit 1"
)

REM  Check if proxy (4000) is running
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:4000/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo [*] Starting Anthropic proxy on port 4000...
    pushd "%STACK_DIR%"
    start /B "" python -u -m src.proxy.server 127.0.0.1 4000 > "%STACK_DIR%\logs\proxy.log" 2>&1
    popd
    powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i=0; $i -lt 15; $i++) { try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:4000/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
)

REM  Check if user requested GUI
if "%~1"=="--gui" goto open_gui
if "%~1"=="gui" goto open_gui

REM  Run Claude Code CLI in current directory
"%BUN_EXE%" "%CLI_BUNDLE%" %*
exit /b %ERRORLEVEL%

:open_gui
echo [+] Opening HCS Coder Web GUI at http://127.0.0.1:4000/gui ...
start http://127.0.0.1:4000/gui
exit /b 0
