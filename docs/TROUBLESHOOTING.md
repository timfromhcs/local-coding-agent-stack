# Battle-Tested Troubleshooting & Resolution Guide

This guide documents concrete engineering obstacles encountered and solved during the end-to-end autonomous build.

---

## 1. Flash Attention Flag Syntax in llama.cpp

### Symptom
`llama-server` crashed immediately on startup with:
```text
invalid argument: -fa
```

### Cause
In modern llama.cpp builds (b11000+), Flash Attention expects an explicit toggle parameter (`on`, `off`, `auto`), not a bare boolean flag.

### Resolution
Update launch scripts to pass:
```bash
-fa on
```
Verified in `scripts/run_llama_server.py`.

---

## 2. Integrated GPU (iGPU) Context Window & Memory Allocation

### Symptom
Running full Claude Code CLI with default options caused 12+ minute prompt evaluation pauses or out-of-memory errors on AMD Radeon 680M integrated graphics.

### Cause
Claude Code injects 19 tool schemas and extensive system prompts (~15,000 to 20,000 tokens) on each turn. Without KV-cache quantization and context limits, the shared DDR5 RAM bandwidth is saturated.

### Resolution
1. Set llama-server context limit to 32,768 tokens: `-c 32768`.
2. Enable 8-bit quantized KV-cache: `-ctk q8_0 -ctv q8_0`.
3. Enable Speculative Decoding via n-gram cache: `--spec-type ngram-mod`.
4. When executing headless smoke tests or fast commands, pass `--bare` and `--tools ""` to eliminate unnecessary schema serializations.

---

## 3. Windows PowerShell Stdin Blocking in Headless Mode

### Symptom
Subprocess execution of `bun ./dist/cli.mjs --print "..."` hung indefinitely until reaching process timeout.

### Cause
Claude Code checks `process.stdin` for piped data. When launched via `subprocess.run` without stdin redirection, Node/Bun waits for stdin closure before rendering completion output:
```text
Warning: no stdin data received in 3s, proceeding without it.
```

### Resolution
Always pass `stdin=subprocess.DEVNULL` (or `< /dev/null` in bash) when running non-interactive headless CLI commands.

---

## 4. Commander Option Parsing Conflict (`-d2e`)

### Symptom
Claude Code failed with:
```text
error: unknown short option '-d2e'
```

### Cause
Commander v13 strict option parsing treats multiple letters after a single hyphen as chained short options (`-d`, `-2`, `-e`). The upstream codebase contained `-d2e, --debug-to-stderr`.

### Resolution
Removed the colliding short option and used long flag `--debug-to-stderr` exclusively in `claude-code-full/src/main.tsx`.

---

## 5. Port Collision & Zombie Server Processes

### Symptom
Proxy failed to bind with:
```text
OSError: [WinError 10048] Only one usage of each socket address is normally permitted
```

### Cause
Previous Python background tasks were terminated abruptly, leaving orphaned Python socket listeners on port 4000.

### Resolution
Run PID-based cleanup before starting:
```powershell
Get-NetTCPConnection -LocalPort 4000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
Stored active PIDs in `proxy.pid` and `llama_server.pid` for clean lifecycle management.
