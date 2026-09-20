#!/usr/bin/env python3
"""
Launcher script for Anthropic Proxy Server.
"""

import sys
import os
import time
import subprocess
import urllib.request
import json
from pathlib import Path

def wait_for_health(host="127.0.0.1", port=4000, timeout=30):
    url = f"http://{host}:{port}/health"
    start = time.time()
    print(f"Waiting for proxy health check at {url}...")
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"Proxy is HEALTHY! Status: {data}")
                    return True
        except Exception:
            time.sleep(0.5)
    print(f"Timed out waiting for proxy after {timeout} seconds.")
    return False

def main():
    host = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 4000
    wait = "--wait" in sys.argv

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = open(log_dir / "proxy.log", "w", encoding="utf-8")

    cmd = [sys.executable, "-u", "-m", "src.proxy.server", host, str(port)]
    print(f"Launching proxy: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True
    )

    Path("proxy.pid").write_text(str(proc.pid))
    print(f"Proxy started with PID {proc.pid}")

    if wait:
        ok = wait_for_health(host, port)
        if not ok:
            sys.exit(1)

if __name__ == "__main__":
    main()
