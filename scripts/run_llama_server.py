#!/usr/bin/env python3
"""
Launcher script for llama-server with Vulkan acceleration, KV-cache quantization,
and speculative decoding.
"""

import os
import sys
import subprocess
import time
import urllib.request
import json
import argparse
from pathlib import Path

def get_llama_server_binary():
    # 1. Custom env var
    if "LLAMA_SERVER_BIN" in os.environ:
        p = Path(os.environ["LLAMA_SERVER_BIN"])
        if p.exists():
            return str(p.resolve())

    # 2. Local extracted Windows Vulkan binary
    win_bin = Path("bin/llama-vulkan/llama-server.exe")
    if win_bin.exists():
        return str(win_bin.resolve())

    # 3. Source build path
    build_bin_win = Path("llama-src/build/bin/Release/llama-server.exe")
    if build_bin_win.exists():
        return str(build_bin_win.resolve())
    build_bin_linux = Path("llama-src/build/bin/llama-server")
    if build_bin_linux.exists():
        return str(build_bin_linux.resolve())

    # 4. PATH search
    system_bin = shutil_which("llama-server")
    if system_bin:
        return system_bin

    raise FileNotFoundError("Could not locate llama-server executable.")

def shutil_which(cmd):
    import shutil
    return shutil.which(cmd)

def wait_for_health(host="127.0.0.1", port=8080, timeout=60):
    url = f"http://{host}:{port}/health"
    start = time.time()
    print(f"Waiting for llama-server health check at {url}...")
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"llama-server is HEALTHY! Status: {data}")
                    return True
        except Exception:
            time.sleep(1)
    print(f"Timed out waiting for llama-server after {timeout} seconds.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Start llama-server")
    parser.add_argument("--model", default="models/NeoHorse-1-4B.Q4_K_M.gguf", help="Path to GGUF model")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind")
    parser.add_argument("--ngl", type=int, default=99, help="Number of GPU layers")
    parser.add_argument("--ctx-size", type=int, default=32768, help="Context size")
    parser.add_argument("--threads", type=int, default=12, help="Number of threads")
    parser.add_argument("--spec-type", default="ngram-mod", help="Speculative decoding type")
    parser.add_argument("--no-vulkan", action="store_true", help="Force CPU backend (ngl=0)")
    parser.add_argument("--wait", action="store_true", help="Wait for health check before returning")
    args = parser.parse_args()

    binary = get_llama_server_binary()
    model_path = Path(args.model).resolve()
    if not model_path.exists():
        print(f"Error: Model not found at {model_path}", file=sys.stderr)
        sys.exit(1)

    env = os.environ.copy()
    env["GGML_VK_PREFER_HOST_MEMORY"] = "1"

    ngl = 0 if args.no_vulkan else args.ngl

    cmd = [
        binary,
        "-m", str(model_path),
        "--host", args.host,
        "--port", str(args.port),
        "-c", str(args.ctx_size),
        "-t", str(args.threads),
        "-ngl", str(ngl),
        "-ctk", "q8_0",
        "-ctv", "q8_0",
        "-fa", "on",
        "--spec-type", args.spec_type,
    ]

    print(f"Launching llama-server: {' '.join(cmd)}")
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = open(log_dir / "llama_server.log", "w", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True
    )

    pid_file = Path("llama_server.pid")
    pid_file.write_text(str(proc.pid))
    print(f"llama-server started with PID {proc.pid}")

    if args.wait:
        healthy = wait_for_health(args.host, args.port)
        if not healthy:
            print("llama-server failed health check. Log snippet:")
            with open(log_dir / "llama_server.log", "r", encoding="utf-8") as f:
                print(f.read()[-2000:])
            sys.exit(1)

if __name__ == "__main__":
    main()
