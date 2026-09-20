#!/usr/bin/env python3
"""
Anthropic Messages API Proxy Server.
Binds to port 4000, proxies requests to local llama-server (port 8080),
supports streaming SSE, tool calling, and RSI trace logging.
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any

from src.proxy.translator import anthropic_to_openai_request, openai_to_anthropic_response

UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "http://127.0.0.1:8080/v1/chat/completions")
PROXY_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "4000"))
RSI_RAW_LOG_DIR = Path(os.environ.get("RSI_RAW_LOG_DIR", "rsi_data/raw"))

def log_rsi_interaction(prompt_body: Dict[str, Any], resp_body: Dict[str, Any], latency_ms: float, success: bool):
    """Save interaction trace for the RSI loop daemon."""
    try:
        RSI_RAW_LOG_DIR.mkdir(parents=True, exist_ok=True)
        trace_file = RSI_RAW_LOG_DIR / f"trace_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}.json"
        entry = {
            "timestamp": time.time(),
            "latency_ms": latency_ms,
            "success": success,
            "request": prompt_body,
            "response": resp_body
        }
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
    except Exception as e:
        print(f"[Proxy] Warning: Failed to log RSI trace: {e}", file=sys.stderr)

class AnthropicProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise logging
        print(f"[Proxy] {self.client_address[0]} - {format % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        req_path = urllib.parse.urlparse(self.path).path.rstrip("/")
        print(f"[Proxy GET] {self.path} -> {req_path}", flush=True)
        if req_path in ("/health", ""):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "proxy": "anthropic-messages-v1"}')
            return

        if req_path in ("/v1/models", "/models"):
            models_data = {
                "data": [
                    {"id": "local-coding-agent", "display_name": "Local Coding Agent", "type": "model", "created_at": "2026-09-20T00:00:00Z"},
                    {"id": "claude-3-7-sonnet-20250219", "display_name": "Claude 3.7 Sonnet", "type": "model", "created_at": "2025-02-19T00:00:00Z"},
                    {"id": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet", "type": "model", "created_at": "2024-10-22T00:00:00Z"},
                    {"id": "claude-3-5-haiku-20241022", "display_name": "Claude 3.5 Haiku", "type": "model", "created_at": "2024-10-22T00:00:00Z"},
                    {"id": "auto", "display_name": "Auto Model", "type": "model", "created_at": "2026-09-20T00:00:00Z"}
                ],
                "has_more": False,
                "first_id": "local-coding-agent",
                "last_id": "auto"
            }
            resp_bytes = json.dumps(models_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        req_path = urllib.parse.urlparse(self.path).path.rstrip("/")
        print(f"[Proxy POST] {self.path} -> {req_path}", flush=True)
        if req_path in ("/v1/messages/count_tokens", "/messages/count_tokens"):
            # Estimate token count
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            tokens = max(1, len(raw_body) // 4)
            resp = {"input_tokens": tokens}
            resp_bytes = json.dumps(resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        with open("logs/proxy_requests.log", "a", encoding="utf-8") as f:
            f.write(f"POST {self.path} (req_path: {req_path})\n")

        if req_path not in ("/v1/messages", "/messages"):
            with open("logs/proxy_unknown_paths.log", "a", encoding="utf-8") as f:
                f.write(f"404 REJECTED: POST {self.path} (req_path: {req_path})\n")
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Endpoint not found"}')
            return

        start_time = time.time()
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            anthropic_req = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode("utf-8"))
            return

        req_model = anthropic_req.get("model", "local-coding-agent")
        stream_requested = bool(anthropic_req.get("stream", False))

        # Translate Anthropic request -> OpenAI request
        openai_req = anthropic_to_openai_request(anthropic_req)
        # We handle stream generation from OpenAI response
        openai_req["stream"] = False

        try:
            req_data = json.dumps(openai_req).encode("utf-8")
            forward_req = urllib.request.Request(
                UPSTREAM_URL,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(forward_req, timeout=180) as upstream_resp:
                raw_resp = upstream_resp.read().decode("utf-8")
                openai_json = json.loads(raw_resp)

            # Translate OpenAI response -> Anthropic response
            anthropic_resp = openai_to_anthropic_response(openai_json, req_model=req_model)
            latency_ms = (time.time() - start_time) * 1000.0

            # Log trace for RSI
            log_rsi_interaction(anthropic_req, anthropic_resp, latency_ms, success=True)

            if stream_requested:
                self.handle_streaming_response(anthropic_resp)
            else:
                self.handle_standard_response(anthropic_resp)

        except Exception as err:
            latency_ms = (time.time() - start_time) * 1000.0
            print(f"[Proxy] Error calling upstream {UPSTREAM_URL}: {err}", file=sys.stderr)
            err_resp = {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": f"Upstream proxy error: {str(err)}"
                }
            }
            log_rsi_interaction(anthropic_req, err_resp, latency_ms, success=False)
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(err_resp).encode("utf-8"))

    def handle_standard_response(self, anthropic_resp: Dict[str, Any]):
        resp_bytes = json.dumps(anthropic_resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(resp_bytes)

    def handle_streaming_response(self, anthropic_resp: Dict[str, Any]):
        """Stream Anthropic SSE events to the client."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        msg_id = anthropic_resp.get("id", f"msg_{uuid.uuid4().hex[:12]}")
        model = anthropic_resp.get("model", "local-coding-agent")

        # 1. message_start
        start_evt = {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": anthropic_resp["usage"]["input_tokens"], "output_tokens": 1}
            }
        }
        self.send_sse_event("message_start", start_evt)

        # 2. Content blocks
        for idx, block in enumerate(anthropic_resp.get("content", [])):
            btype = block.get("type")
            if btype == "text":
                self.send_sse_event("content_block_start", {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {"type": "text", "text": ""}
                })
                # Send text delta
                text = block.get("text", "")
                self.send_sse_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {"type": "text_delta", "text": text}
                })
                self.send_sse_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": idx
                })
            elif btype == "tool_use":
                self.send_sse_event("content_block_start", {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {
                        "type": "tool_use",
                        "id": block.get("id", f"toolu_{uuid.uuid4().hex[:8]}"),
                        "name": block.get("name", ""),
                        "input": {}
                    }
                })
                self.send_sse_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(block.get("input", {}))
                    }
                })
                self.send_sse_event("content_block_stop", {
                    "type": "content_block_stop",
                    "index": idx
                })

        # 3. message_delta
        self.send_sse_event("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": anthropic_resp.get("stop_reason", "end_turn"),
                "stop_sequence": None
            },
            "usage": {"output_tokens": anthropic_resp["usage"]["output_tokens"]}
        })

        # 4. message_stop
        self.send_sse_event("message_stop", {"type": "message_stop"})

    def send_sse_event(self, event_type: str, data: Dict[str, Any]):
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()

def run_server(host=PROXY_HOST, port=PROXY_PORT):
    server_address = (host, port)
    httpd = HTTPServer(server_address, AnthropicProxyHandler)
    print(f"Starting Anthropic Proxy server on http://{host}:{port} -> forwarding to {UPSTREAM_URL}")
    httpd.serve_forever()

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else PROXY_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PROXY_PORT
    run_server(host, port)
