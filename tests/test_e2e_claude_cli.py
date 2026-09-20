"""
End-to-End tests executing REAL Claude Code CLI binary.
ZERO MOCKS: runs compiled JS bundle via Bun against the local proxy stack.
"""

import os
import shutil
import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_BUNDLE = PROJECT_ROOT / "claude-code-full" / "dist" / "cli.mjs"

def get_bun_bin() -> str:
    bun_candidates = [
        Path(r"C:\Users\hcsme\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.22_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v22.23.1-win-x64\node_modules\bun\bin\bun.exe"),
        Path.home() / ".bun" / "bin" / "bun.exe",
    ]
    for cand in bun_candidates:
        if cand.exists():
            return str(cand)
    bin_path = shutil.which("bun.exe") or shutil.which("bun")
    assert bin_path, "Bun executable not found on system"
    return bin_path

def test_claude_code_cli_version():
    """Verify patched Claude Code CLI reports custom local version instantly."""
    bun_bin = get_bun_bin()
    proc = subprocess.run(
        [bun_bin, str(CLI_BUNDLE), "--version"],
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15
    )
    assert proc.returncode == 0
    assert "2.0.0-local" in proc.stdout

def test_claude_code_cli_help():
    """Verify patched Claude Code CLI displays command line flags and options."""
    bun_bin = get_bun_bin()
    proc = subprocess.run(
        [bun_bin, str(CLI_BUNDLE), "--help"],
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15
    )
    assert proc.returncode == 0
    assert "--bare" in proc.stdout
    assert "--dangerously-skip-permissions" in proc.stdout

@pytest.mark.slow
def test_claude_code_cli_execution():
    """Verify patched Claude Code CLI runs prompt against local model stack."""
    bun_bin = get_bun_bin()
    env = dict(os.environ)
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:4000"
    env["ANTHROPIC_API_KEY"] = "test-local-key"
    env["ANTHROPIC_MODEL"] = "claude-3-5-sonnet-20241022"
    env["ANTHROPIC_SMALL_FAST_MODEL"] = "claude-3-5-sonnet-20241022"

    proc = subprocess.run(
        [bun_bin, str(CLI_BUNDLE), "--bare", "--tools", "", "--print", "Say CLI_OK"],
        cwd=str(PROJECT_ROOT / "test_sandbox"),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=450
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0
    assert "CLI_OK" in combined
