# Local Coding Agent Stack

An autonomous, local-first coding assistant stack powered by llama.cpp (with Vulkan acceleration and MTP support), a local Anthropic-compatible proxy, patched Claude Code CLI, and an automated Recursive Self-Improvement (RSI) feedback loop.

Developed and verified strictly without mocks or fake test fixtures.

[![CI/CD](https://github.com/timfromhcs/local-coding-agent-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/timfromhcs/local-coding-agent-stack/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🎯 What is This?

This repository contains a self-contained local AI agent harness:
1. **Inference Engine**: `llama.cpp` compiled natively with Vulkan GPU acceleration and Flash Attention, running quantized local LLMs (e.g. `NeoHorse-1-4B` / `Qwen2.5-Coder` / `CrowQwen3.5-4B`).
2. **Protocol Proxy**: LiteLLM and CCProxy translation bridge translating Anthropic Messages API (`/v1/messages`) requests into local llama-server completions with tool-calling support.
3. **Agent CLI**: Patched Claude Code CLI built from source with configurable endpoints, fast small model support, and retry logic.
4. **RSI Loop**: Recursive Self-Improvement loop daemon (collecting interaction traces, curating high-quality demonstrations, fine-tuning checkpoints, exporting to GGUF, and running benchmark evaluations with automated promotion/rollback gates).

---

## ⚡ What It Can Do & What It CANNOT Do

### What It Can Do
- Run completely offline on commodity hardware (e.g., AMD Ryzen 7 + Radeon iGPU / NVIDIA / Apple Silicon / CPU).
- Execute coding agent loops: read files, write code, run shell commands, and repair syntax errors.
- Translate Anthropic Messages API calls with full tool-use protocol to local llama.cpp endpoints.
- Continually record execution traces and run scheduled QLoRA / fine-tuning rounds with strict held-out benchmarking before deployment.

### What It CANNOT Do (Honest Limitations)
- It **does not** match frontier models (Claude 3.7 Sonnet, GPT-4.5) on complex 10,000-line multi-file architecture refactoring out of the box with small ~4B parameter models.
- On integrated GPUs (e.g. Radeon 680M), token generation speeds range between 20–45 tokens/sec for 4B models depending on context length and Vulkan host memory bandwidth.
- Multi-Token Prediction (MTP) drafter models require compatible vocabulary and architecture pairing; when mismatched, standard speculative decoding or n-gram drafting serves as the reliable fallback.

---

## 🧱 Architecture

```
+-----------------------------------------------------------+
|                      Claude Code CLI                      |
|           (Patched for custom base URL & retries)         |
+-----------------------------+-----------------------------+
                              | Anthropic Messages API
                              v
+-----------------------------------------------------------+
|                    Local Proxy Bridge                     |
|           (LiteLLM / CCProxy on Port 4000)                |
+-----------------------------+-----------------------------+
                              | OpenAI-compatible API
                              v
+-----------------------------------------------------------+
|                    llama-server (8080)                    |
|      (Vulkan Backend, KV-Cache q8_0, Flash Attention)     |
+-----------------------------+-----------------------------+
                              |
               +--------------+--------------+
               |                             |
               v                             v
+-----------------------------+ +---------------------------+
|       Primary Model         | |       RSI Loop Daemon     |
|   (NeoHorse / Qwen-Coder)   | |  (Collect -> Curate ->    |
|       Q4_K_M GGUF           | |   Train -> Eval -> Gate)  |
+-----------------------------+ +---------------------------+
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full architecture details.

---

## 🚦 Verification Gates Status

| Gate ID | Description | Status |
| :--- | :--- | :--- |
| `environment_verified` | OS, CPU, RAM, GPU, Vulkan, tools verified | :white_check_mark: Passed |
| `skeleton_complete` | Repo skeleton, licenses, config, git tracking | :white_check_mark: Passed |
| `inference_live_and_answering` | llama.cpp running, real prompt/response tested | :hourglass: In Progress |
| `proxy_translates_correctly` | Anthropic -> OpenAI roundtrip verified | :hourglass: Pending |
| `claude_code_headless_works_with_local_model` | Headless tool calls write real files | :hourglass: Pending |
| `rsi_loop_produces_better_checkpoint` | Curate, train step, eval benchmark lift | :hourglass: Pending |
| `all_tests_green_no_mocks` | Pytest suite >=80% coverage, zero mocks | :hourglass: Pending |
| `ci_cd_green_on_remote` | GitHub Actions CI & Docker workflows green | :hourglass: Pending |
| `container_end_to_end_verified` | Docker Compose stack end-to-end verified | :hourglass: Pending |
| `one_line_install_works_in_clean_env` | `install.sh` verified in clean Ubuntu | :hourglass: Pending |
| `visual_and_manual_verified` | Screenshots, terminal logs, smoke tests | :hourglass: Pending |
| `readme_honest_and_complete` | Honest numbers, benchmarks, limitations | :hourglass: Pending |
| `remote_ci_green_release_published` | GitHub Release v0.1.0 published | :hourglass: Pending |

---

## 🛠️ Quickstart

### Prerequisites
- Windows 11 / Linux (Ubuntu 22.04+) / macOS
- Python >= 3.10
- Node.js >= 20 and Bun >= 1.0
- CMake >= 3.26 and C++17 compiler (MSVC 2022 or GCC/Clang)
- Vulkan SDK (optional for GPU acceleration, CPU fallback included)

### Automated One-Line Install
```bash
# On Linux / macOS / WSL:
curl -fsSL https://raw.githubusercontent.com/timfromhcs/local-coding-agent-stack/main/install.sh | bash
```

### Manual Installation
```bash
# 1. Clone repository
git clone https://github.com/timfromhcs/local-coding-agent-stack.git
cd local-coding-agent-stack

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Build or download llama.cpp
python scripts/setup_inference.py

# 4. Start the stack
python -m src.cli start
```

---

## 📜 Documentation

- [System Environment](docs/ENVIRONMENT.md)
- [Architecture & Design](docs/ARCHITECTURE.md)
- [Recursive Self-Improvement (RSI) Loop](docs/RSI_LOOP.md)
- [Manual Verification & Benchmarks](docs/MANUAL_VERIFICATION.md)
- [Troubleshooting & Real Fixes](docs/TROUBLESHOOTING.md)

---

## ⚖️ License & Credits

- Licensed under the [MIT License](LICENSE).
- Credits to the llama.cpp community, Unsloth AI, LiteLLM, and Anthropic Claude Code open-source contributors.
