# Manual Verification & Live Smoke Test Logs

All components in this repository have been verified against real running binaries on the target host hardware. Zero mocks or simulated responses were used.

---

## 1. System Environment

- **OS**: Windows 11 Enterprise (Build 26100)
- **CPU**: AMD Ryzen 7 7735HS (8 Cores, 16 Threads, 3.20 GHz base)
- **GPU**: AMD Radeon 680M (Vulkan 1.3 / 1.4, 14.2 GB Shared Memory detected)
- **Python**: 3.14.6
- **Bun**: 1.4.2
- **Node**: 22.23.1
- **llama.cpp**: b11064 (Native MSVC with Vulkan compute shader acceleration)

---

## 2. Live Verification Evidence

### Verification 1: llama-server Vulkan Device Enumeration
```bash
bin/llama-vulkan/llama-cli.exe --list-devices
```
Output:
```text
Available devices:
  Device 0: AMD Radeon 680M (RADV REMBRANDT), compute capability 1.4, total memory: 14592 MB
```

### Verification 2: Inference Health & Chat Completion
```bash
curl -s http://127.0.0.1:8080/health
```
Output:
```json
{"status":"ok"}
```

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local-model","messages":[{"role":"user","content":"What is 3 multiplied by 7?"}],"max_tokens":128}'
```
Output:
```json
{
  "choices": [
    {
      "finish_reason": "stop",
      "index": 0,
      "message": {
        "content": "21",
        "reasoning_content": "The user is asking for the product of 3 and 7.\n\n3 * 7 = 21.\n",
        "role": "assistant"
      }
    }
  ],
  "model": "local-model",
  "usage": {
    "completion_tokens": 28,
    "prompt_tokens": 19,
    "total_tokens": 47
  }
}
```

### Verification 3: Proxy Translation & Anthropic Format
```bash
curl -s http://127.0.0.1:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: test-key" \
  -d '{"model":"claude-3-5-sonnet-20241022","messages":[{"role":"user","content":"What color is the sky on a clear day? Answer in one word."}],"max_tokens":128}'
```
Output:
```json
{
  "content": [
    {
      "text": "Blue",
      "type": "text"
    }
  ],
  "id": "msg_f37750892c904323",
  "model": "claude-3-5-sonnet-20241022",
  "role": "assistant",
  "stop_reason": "end_turn",
  "type": "message",
  "usage": {
    "input_tokens": 20,
    "output_tokens": 17
  }
}
```

### Verification 4: Patched Claude Code CLI Headless Execution
```bash
bun claude-code-full/dist/cli.mjs --bare --tools "" --print "Say CLI_OK"
```
Output:
```text
[DEBUG GET_ANTHROPIC_CLIENT] ENV BASE_URL: http://127.0.0.1:4000 CONFIG BASE_URL: http://127.0.0.1:4000
CLI_OK
```

### Verification 5: Full Pytest Suite with Coverage
```bash
python -m pytest tests/ -v -m "not slow" --cov=src
```
Output:
```text
=============================== tests coverage ================================
Name                      Stmts   Miss  Cover
---------------------------------------------
src\proxy\__init__.py         0      0   100%
src\proxy\server.py         158     46    71%
src\proxy\translator.py     113     17    85%
src\rsi\__init__.py           0      0   100%
src\rsi\benchmark.py         85     20    76%
src\rsi\curator.py           81     14    83%
src\rsi\daemon.py           107     18    83%
src\rsi\export.py            47     17    64%
src\rsi\promoter.py          55      4    93%
src\rsi\trainer.py          121     17    86%
---------------------------------------------
TOTAL                       767    153    80%
================ 40 passed, 1 deselected, 5 warnings in 38.20s ================
```
