"""
Integration tests against LIVE llama-server.
ZERO MOCKS: every test sends real HTTP requests to the active llama.cpp process.
"""

import pytest
import urllib.request
import json
import time

LLAMA_URL = "http://127.0.0.1:8080"

def _is_server_available():
    try:
        req = urllib.request.Request(f"{LLAMA_URL}/health")
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

pytestmark = pytest.mark.skipif(
    not _is_server_available(),
    reason="llama-server not running on http://127.0.0.1:8080"
)

def test_live_inference_health():
    """Verify live inference server is healthy and responding."""
    req = urllib.request.Request(f"{LLAMA_URL}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "ok"

def test_live_inference_chat_completion():
    """Verify live model generates real tokens via OpenAI chat completions format."""
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "user", "content": "What is 3 multiplied by 7? Reply with only the number."}
        ],
        "temperature": 0.0,
        "max_tokens": 128
    }
    t0 = time.perf_counter()
    req = urllib.request.Request(
        f"{LLAMA_URL}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.perf_counter() - t0

    assert "choices" in data and len(data["choices"]) > 0
    content = data["choices"][0]["message"]["content"]
    assert "21" in content
    assert elapsed < 30.0

def test_live_inference_robustness_empty_input():
    """Verify inference server does not crash on empty/minimal input."""
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "user", "content": " "}
        ],
        "max_tokens": 4
    }
    req = urllib.request.Request(
        f"{LLAMA_URL}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "choices" in data
