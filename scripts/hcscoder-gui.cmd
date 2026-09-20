@echo off
set "STACK_DIR=E:\AI"

:: Check if llama-server (8080) is running
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo [*] Starting llama-server on port 8080...
    start /B "" python "%STACK_DIR%\scripts\run_llama_server.py"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } } catch { Start-Sleep -Seconds 1 } }; exit 1"
)

:: Check if proxy (4000) is running
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:4000/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
    echo [*] Starting Anthropic proxy on port 4000...
    pushd "%STACK_DIR%"
    start /B "" python -u -m src.proxy.server 127.0.0.1 4000
    popd
    powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i=0; $i -lt 15; $i++) { try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:4000/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
)

echo [✓] Local AI stack is live!
echo [✓] Opening HCS Coder Web GUI at http://127.0.0.1:4000/gui ...
start http://127.0.0.1:4000/gui
