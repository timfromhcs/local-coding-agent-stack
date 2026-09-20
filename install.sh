#!/usr/bin/env bash
# ==============================================================================
# Local Coding Agent Stack — One-Line Automated Installer
# Supported: Linux (x86_64, aarch64), macOS (Apple Silicon, Intel), Windows (WSL / Git Bash)
# Can be run from any directory (auto-clones repository if not present).
# ==============================================================================

set -euo pipefail

BOLD="$(tput bold 2>/dev/null || true)"
GREEN="$(tput setaf 2 2>/dev/null || true)"
YELLOW="$(tput setaf 3 2>/dev/null || true)"
RED="$(tput setaf 1 2>/dev/null || true)"
RESET="$(tput sgr0 2>/dev/null || true)"

log_info() { echo "${GREEN}[+]${RESET} $*"; }
log_warn() { echo "${YELLOW}[!]${RESET} $*"; }
log_err()  { echo "${RED}[ERROR]${RESET} $*" >&2; }

echo "${BOLD}================================================================${RESET}"
echo "${BOLD}       Local Coding Agent Stack — Unified Installer             ${RESET}"
echo "${BOLD}================================================================${RESET}"

# 0. Ensure Repository Directory
REPO_DIR="$PWD"
if [ ! -f "config/requirements.txt" ] || [ ! -f "src/proxy/server.py" ]; then
  TARGET_DIR="$PWD/local-coding-agent-stack"
  if [ -f "$TARGET_DIR/config/requirements.txt" ]; then
    log_info "Using existing repository at $TARGET_DIR"
    REPO_DIR="$TARGET_DIR"
  else
    log_warn "Repository not detected in current directory."
    log_info "Cloning https://github.com/timfromhcs/local-coding-agent-stack.git into $TARGET_DIR..."
    if command -v git >/dev/null 2>&1; then
      git clone https://github.com/timfromhcs/local-coding-agent-stack.git "$TARGET_DIR"
    else
      log_warn "git not found, downloading repository ZIP..."
      curl -fsSL https://github.com/timfromhcs/local-coding-agent-stack/archive/refs/heads/main.zip -o /tmp/repo.zip
      unzip -q /tmp/repo.zip -d /tmp/
      rm -rf "$TARGET_DIR"
      mv /tmp/local-coding-agent-stack-main "$TARGET_DIR"
      rm -f /tmp/repo.zip
    fi
    REPO_DIR="$TARGET_DIR"
  fi
  cd "$REPO_DIR"
fi

log_info "Working directory: $REPO_DIR"

# 1. OS & Architecture Detection
OS="$(uname -s)"
ARCH="$(uname -m)"
log_info "Detected OS: $OS ($ARCH)"

case "$OS" in
  Linux*)   PLATFORM="linux" ;;
  Darwin*)  PLATFORM="macos" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  *) log_err "Unsupported OS: $OS"; exit 1 ;;
esac

# 2. Hardware Checks
MEM_TOTAL_KB=0
if [ "$PLATFORM" = "linux" ]; then
  MEM_TOTAL_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
elif [ "$PLATFORM" = "macos" ]; then
  MEM_TOTAL_BYTES=$(sysctl -n hw.memsize)
  MEM_TOTAL_KB=$((MEM_TOTAL_BYTES / 1024))
fi

MEM_TOTAL_GB=$((MEM_TOTAL_KB / 1024 / 1024))
log_info "Detected RAM: ${MEM_TOTAL_GB} GB"
if [ "$MEM_TOTAL_GB" -gt 0 ] && [ "$MEM_TOTAL_GB" -lt 8 ]; then
  log_warn "At least 8 GB RAM recommended for 1.4B-4B local models. Proceeding with caution."
fi

# 3. Check / Install Prerequisites
check_tool() {
  command -v "$1" >/dev/null 2>&1
}

log_info "Verifying core dependencies..."

if ! check_tool python3; then
  log_err "Python 3 is required. Please install Python >= 3.10."
  exit 1
fi

PYTHON_BIN="python3"
log_info "Using Python: $($PYTHON_BIN --version)"

if ! check_tool bun; then
  log_warn "Bun not found. Installing bun..."
  curl -fsSL https://bun.sh/install | bash
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
fi
log_info "Using Bun: $(bun --version)"

# 4. Set up Python Environment
log_info "Setting up Python environment and requirements..."
if [ ! -d ".venv" ]; then
  $PYTHON_BIN -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate || source .venv/Scripts/activate 2>/dev/null || true

pip install --upgrade pip
pip install -r config/requirements.txt

# 5. Build Claude Code CLI bundle
log_info "Compiling Claude Code CLI bundle..."
if [ -d "claude-code-full" ]; then
  (cd claude-code-full && bun install && bun scripts/build-bundle.ts)
else
  log_warn "claude-code-full directory missing, skipping CLI build."
fi

# 6. Verify Model Weights
mkdir -p models
MODEL_PATH="models/NeoHorse-1-4B.Q4_K_M.gguf"
if [ ! -f "$MODEL_PATH" ]; then
  log_warn "Model weights not found at $MODEL_PATH."
  log_info "Downloading NeoHorse-1-4B.Q4_K_M.gguf from HuggingFace..."
  curl -L -o "$MODEL_PATH" "https://huggingface.co/mradermacher/NeoHorse-1-4B-GGUF/resolve/main/NeoHorse-1-4B.Q4_K_M.gguf" || {
    log_err "Download failed. Please place NeoHorse-1-4B.Q4_K_M.gguf into models/ manually."
  }
else
  log_info "Verified model weights: $MODEL_PATH"
fi

# 7. Configure Claude Code Environment
log_info "Configuring Anthropic local settings..."
mkdir -p "$HOME/.claude"
cat << 'EOF' > "$HOME/.claude/settings.json"
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
    "ANTHROPIC_AUTH_TOKEN": "local-key",
    "ANTHROPIC_MODEL": "auto",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "auto",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "auto"
  }
}
EOF

# 8. Complete
echo "${BOLD}================================================================${RESET}"
echo "${GREEN}${BOLD}Installation Complete! Stack is ready to run.${RESET}"
echo ""
echo "To launch the full local stack in $REPO_DIR:"
echo "  1. Start llama-server:  python scripts/run_llama_server.py"
echo "  2. Start Proxy:         python -m src.proxy.server"
echo "  3. Start RSI Daemon:    python -m src.rsi.daemon loop"
echo "  4. Run Claude Code:     bun claude-code-full/dist/cli.mjs"
echo ""
echo "Or via Docker Compose:    docker compose up -d"
echo "${BOLD}================================================================${RESET}"
