import os
import sys
import time
import subprocess
import urllib.request

def restart_proxy():
    # Kill existing python proxy on port 4000
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "Get-NetTCPConnection -LocalPort 4000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"],
            text=True
        ).strip()
        for line in out.splitlines():
            pid = line.strip()
            if pid.isdigit() and int(pid) > 0:
                print(f"Killing old proxy PID {pid}...")
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    except Exception as e:
        print(f"Cleanup check: {e}")

    time.sleep(0.5)

    # Start new proxy
    print("Starting new proxy on http://127.0.0.1:4000 ...")
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "src.proxy.server", "127.0.0.1", "4000"],
        cwd="E:\\AI"
    )

    with open("proxy.pid", "w") as f:
        f.write(str(proc.pid))

    # Health check
    time.sleep(1)
    for _ in range(10):
        try:
            with urllib.request.urlopen("http://127.0.0.1:4000/health", timeout=2) as resp:
                if resp.status == 200:
                    print(f"Proxy successfully restarted with PID {proc.pid}!")
                    return True
        except Exception:
            time.sleep(0.5)

    print("Proxy failed to respond in time.")
    return False

if __name__ == "__main__":
    restart_proxy()
