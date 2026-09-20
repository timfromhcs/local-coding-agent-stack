"""
Integration tests against LIVE Proxy Server (port 4000).
ZERO MOCKS: sends real HTTP requests in Anthropic Messages API format.
"""

import pytest
import urllib.request
import json
import time

PROXY_URL = "http://127.0.0.1:4000"

def _is_proxy_available():
    try:
        req = urllib.request.Request(f"{PROXY_URL}/health")
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

pytestmark = pytest.mark.skipif(
    not _is_proxy_available(),
    reason="proxy server not running on http://127.0.0.1:4000"
)

def test_proxy_health():
    """Verify proxy server is alive and reports proxy status."""
    req = urllib.request.Request(f"{PROXY_URL}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "ok"
        assert data.get("proxy") == "anthropic-messages-v1"

def test_proxy_models_endpoint():
    """Verify proxy satisfies Anthropic client model enumeration."""
    req = urllib.request.Request(f"{PROXY_URL}/v1/models")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "data" in data
        assert any(m["id"] == "claude-3-5-sonnet-20241022" for m in data["data"])

def test_proxy_roundtrip_message():
    """Verify proxy translates Anthropic /v1/messages request and returns Anthropic response."""
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "system": "You are a concise assistant.",
        "messages": [
            {"role": "user", "content": "What color is the sky on a clear day? Answer in one word."}
        ],
        "max_tokens": 128
    }
    req = urllib.request.Request(
        f"{PROXY_URL}/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": "test-key"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))

    assert data.get("type") == "message"
    assert data.get("role") == "assistant"
    assert "content" in data and len(data["content"]) > 0
    text = data["content"][0]["text"].lower()
    assert "blue" in text
    assert data.get("usage", {}).get("output_tokens", 0) > 0

def test_proxy_streaming():
    """Verify proxy SSE streaming translates OpenAI stream chunks to Anthropic SSE events."""
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {"role": "user", "content": "Say hello."}
        ],
        "max_tokens": 64,
        "stream": True
    }
    req = urllib.request.Request(
        f"{PROXY_URL}/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": "test-key"}
    )
    events_received = []
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        assert "text/event-stream" in resp.headers.get("Content-Type", "")
        for line in resp:
            line_str = line.decode("utf-8").strip()
            if line_str.startswith("event:"):
                events_received.append(line_str)
            if "message_stop" in line_str:
                break

    assert len(events_received) > 0
    assert any("message_start" in ev or "content_block_delta" in ev or "message_stop" in ev for ev in events_received)
