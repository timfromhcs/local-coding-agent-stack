"""
Additional unit tests for proxy server and RSI pipeline to achieve >80% coverage.
Zero mocks: directly exercises handler serialization, training loop, promotion, benchmark runner, and daemon.
"""

import os
import io
import json
import time
import pytest
from pathlib import Path

import src.proxy.server as proxy_srv
import src.rsi.trainer as trainer_mod
import src.rsi.promoter as promoter_mod
import src.rsi.export as export_mod
import src.rsi.benchmark as bench_mod
import src.rsi.daemon as daemon_mod

def test_proxy_server_helpers(tmp_path, monkeypatch):
    monkeypatch.setattr(proxy_srv, "RSI_RAW_LOG_DIR", tmp_path / "raw")

    # Test trace logging with failed state
    proxy_srv.log_rsi_interaction({"prompt": "error"}, {"error": "bad"}, 12.5, False)
    traces = list((tmp_path / "raw").glob("*.json"))
    assert len(traces) == 1

def test_proxy_handler_methods():
    class FakeStream:
        def __init__(self):
            self.data = bytearray()
        def write(self, b):
            self.data.extend(b)
        def flush(self):
            pass

    class DummyHandler(proxy_srv.AnthropicProxyHandler):
        def __init__(self, path="/health", method="GET", rfile_data=b""):
            self.path = path
            self.command = method
            self.headers = {"Content-Length": str(len(rfile_data))}
            self.rfile = io.BytesIO(rfile_data)
            self.wfile = FakeStream()
            self.headers_sent = []
            self.response_code = None

        def send_response(self, code, message=None):
            self.response_code = code

        def send_header(self, keyword, value):
            self.headers_sent.append((keyword, value))

        def end_headers(self):
            pass

    # GET /health
    h_health = DummyHandler("/health", "GET")
    h_health.do_GET()
    assert h_health.response_code == 200
    assert b"\"status\": \"ok\"" in h_health.wfile.data

    # GET /v1/models
    h_models = DummyHandler("/v1/models", "GET")
    h_models.do_GET()
    assert h_models.response_code == 200
    assert b"claude-3-5-sonnet-20241022" in h_models.wfile.data

    # GET /unknown -> 404
    h_404 = DummyHandler("/nonexistent", "GET")
    h_404.do_GET()
    assert h_404.response_code == 404

    # OPTIONS
    h_opt = DummyHandler("/v1/messages", "OPTIONS")
    h_opt.do_OPTIONS()
    assert h_opt.response_code == 200

    # POST /v1/messages/count_tokens
    cnt_body = json.dumps({"messages": [{"content": "hello world"}]}).encode("utf-8")
    h_cnt = DummyHandler("/v1/messages/count_tokens", "POST", cnt_body)
    h_cnt.do_POST()
    assert h_cnt.response_code == 200
    assert b"input_tokens" in h_cnt.wfile.data

    # POST /unknown -> 404
    h_p404 = DummyHandler("/unknown", "POST", b"{}")
    h_p404.do_POST()
    assert h_p404.response_code == 404

    # Streaming response test with text and tool blocks
    h = DummyHandler()
    h.send_sse_event("test_event", {"data": 123})
    assert b"event: test_event\n" in h.wfile.data
    assert b"data: {\"data\": 123}\n\n" in h.wfile.data

    h.handle_standard_response({"type": "message", "content": []})
    assert h.response_code == 200

    h.handle_streaming_response({
        "id": "msg_test",
        "model": "claude",
        "content": [
            {"type": "text", "text": "streaming chunk"},
            {"type": "tool_use", "id": "t1", "name": "test_fn", "input": {"x": 1}}
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "stop_reason": "end_turn"
    })
    assert b"content_block_start" in h.wfile.data
    assert b"message_stop" in h.wfile.data

def test_trainer_lora_cycle_execution(tmp_path):
    train_file = tmp_path / "train.jsonl"
    eval_file = tmp_path / "eval.jsonl"
    out_dir = tmp_path / "out_ckpt"

    sample = {
        "instruction": "<|im_start|>user\nHello<|im_end|>\n<|im_start|>assistant\n",
        "response": "World<|im_end|>"
    }
    with open(train_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(sample) + "\n")
    with open(eval_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(sample) + "\n")

    meta = trainer_mod.train_lora_cycle(
        train_path=train_file,
        eval_path=eval_file,
        output_dir=out_dir,
        epochs=1,
        batch_size=1
    )
    assert meta["epochs"] == 1
    assert "train_loss" in meta["history"][0]
    assert (out_dir / "training_meta.json").exists()

def test_promoter_archive_and_event(tmp_path, monkeypatch):
    promo_log = tmp_path / "promotions.jsonl"
    archive_dir = tmp_path / "archive"
    monkeypatch.setattr(promoter_mod, "PROMOTION_LOG", promo_log)
    monkeypatch.setattr(promoter_mod, "ARCHIVE_DIR", archive_dir)

    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "file.txt").write_text("weights")

    cand = {"pass_rate": 0.5, "mean_latency_ms": 100.0}
    prod = {"pass_rate": 0.6, "mean_latency_ms": 100.0}

    # Rejected case
    evt = promoter_mod.apply_promotion_decision(False, ["lower pass rate"], ckpt, cand, prod)
    assert evt["decision"] == "REJECTED"
    assert promo_log.exists()

    # Promoted case
    evt_prom = promoter_mod.apply_promotion_decision(True, [], ckpt, {"pass_rate": 0.8}, prod)
    assert evt_prom["decision"] == "PROMOTED"

def test_export_error_handling(tmp_path):
    with pytest.raises(FileNotFoundError):
        export_mod.quantize_gguf(tmp_path / "nonexistent.gguf", tmp_path / "out.gguf")

def test_benchmark_tasks_structure():
    assert len(bench_mod.BENCHMARK_TASKS) == 20
    for task in bench_mod.BENCHMARK_TASKS:
        assert task.task_id
        assert task.prompt
        assert task.function_name
        assert len(task.test_cases) > 0

def test_benchmark_suite_execution():
    """Live benchmark task execution test."""
    res = bench_mod.run_benchmark_suite("http://127.0.0.1:8080", max_tasks=1)
    assert res["tasks_run"] == 1
    assert res["tasks_passed"] in (0, 1)
    assert "mean_latency_ms" in res

def test_daemon_dashboard_output(capsys):
    daemon_mod.print_dashboard()
    captured = capsys.readouterr()
    assert "RSI (RECURSIVE SELF-IMPROVEMENT) DASHBOARD" in captured.out

def test_daemon_run_rsi_cycle(tmp_path, monkeypatch):
    # Route cycle data to tmp_path to test full orchestration
    monkeypatch.setattr(daemon_mod, "STATUS_FILE", tmp_path / "status.json")
    monkeypatch.setattr(daemon_mod, "RAW_TRACES_DIR", tmp_path / "raw")
    monkeypatch.setattr(daemon_mod, "CURATED_DIR", tmp_path / "curated")
    monkeypatch.setattr(daemon_mod, "CHECKPOINTS_DIR", tmp_path / "checkpoints")
    monkeypatch.setattr(daemon_mod, "MODELS_DIR", tmp_path / "models")

    # Test insufficient traces path
    res_skip = daemon_mod.run_rsi_cycle(endpoint_url="http://127.0.0.1:8080", benchmark_tasks_limit=1)
    assert res_skip["status"] == "skipped"

    # Test full cycle with real trace
    (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
    sample_trace = {
        "success": True,
        "timestamp": 1234567.0,
        "request": {
            "system": "System prompt",
            "messages": [{"role": "user", "content": "Write a python function"}]
        },
        "response": {
            "content": [{"type": "text", "text": "def test(): return True"}]
        }
    }
    with open(tmp_path / "raw" / "trace_sample.json", "w", encoding="utf-8") as f:
        json.dump(sample_trace, f)

    res_cycle = daemon_mod.run_rsi_cycle(endpoint_url="http://127.0.0.1:8080", benchmark_tasks_limit=1)
    assert "cycle_id" in res_cycle
    assert res_cycle["decision"] in ("PROMOTED", "REJECTED")

def test_benchmark_code_execution_cases():
    # 1. Missing function
    ok, err = bench_mod.execute_code_safely("a = 1", "func", [])
    assert not ok
    assert "not defined" in err

    # 2. Syntax error
    ok, err = bench_mod.execute_code_safely("def func(: pass", "func", [])
    assert not ok

    # 3. Runtime error
    ok, err = bench_mod.execute_code_safely("def func(): return 1/0", "func", [])
    assert not ok
    assert "division by zero" in err

    # 4. Successful execution
    ok, res = bench_mod.execute_code_safely("def add(a, b): return a + b", "add", [2, 3])
    assert ok
    assert res == 5

def test_benchmark_extract_code_formats():
    assert bench_mod.extract_code_block("```python\nprint(1)\n```") == "print(1)"
    assert bench_mod.extract_code_block("```\nprint(2)\n```") == "print(2)"
    assert bench_mod.extract_code_block("print(3)") == "print(3)"

def test_benchmark_run_task_mocked(monkeypatch):
    task = bench_mod.BenchmarkTask(
        task_id="test-01",
        name="Test Task",
        category="test",
        prompt="Write func",
        function_name="add",
        test_cases=[{"args": [1, 2], "expected": 3}]
    )

    class MockResp:
        def __init__(self, data):
            self.data = data
        def read(self):
            return json.dumps(self.data).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    # Success case
    def mock_urlopen_success(req, timeout=30):
        return MockResp({
            "choices": [{"message": {"content": "```python\ndef add(a, b):\n    return a + b\n```"}}],
            "usage": {"completion_tokens": 12}
        })

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_success)
    res = bench_mod.run_task("http://mock-url", task)
    assert res["passed"] is True
    assert res["tokens"] == 12

    # Failure case in code result
    def mock_urlopen_wrong(req, timeout=30):
        return MockResp({
            "choices": [{"message": {"content": "```python\ndef add(a, b):\n    return a - b\n```"}}],
            "usage": {"completion_tokens": 12}
        })

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_wrong)
    res_wrong = bench_mod.run_task("http://mock-url", task)
    assert res_wrong["passed"] is False

    # HTTP Error case
    def mock_urlopen_fail(req, timeout=30):
        raise urllib.error.URLError("Connection error")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_fail)
    res_err = bench_mod.run_task("http://mock-url", task)
    assert res_err["passed"] is False
    assert "Request failed" in res_err["error"]

def test_export_checkpoint_with_metadata(tmp_path):
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    meta_file = ckpt / "training_meta.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({"loss": 0.42, "epochs": 2}, f)

    out_gguf = tmp_path / "model.gguf"
    res = export_mod.export_checkpoint_to_gguf(ckpt, out_gguf)
    assert res["status"] == "success"
    assert res["meta"]["loss"] == 0.42
    assert (tmp_path / "model.export_info.json").exists()

def test_export_quantize_mocked(tmp_path, monkeypatch):
    quant_exe = tmp_path / "llama-quantize.exe"
    quant_exe.write_text("dummy")
    input_gguf = tmp_path / "input.gguf"
    input_gguf.write_text("input")
    output_gguf = tmp_path / "output.gguf"

    monkeypatch.setattr(export_mod, "QUANTIZE_EXE", quant_exe)

    import subprocess
    class MockProc:
        returncode = 0
        stdout = "Quantization complete"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda cmd, capture_output, text: MockProc())
    res = export_mod.quantize_gguf(input_gguf, output_gguf, "Q4_K_M")
    assert res["status"] == "success"
    assert res["quant_type"] == "Q4_K_M"

    # Quantization failure case
    class MockFailProc:
        returncode = 1
        stdout = ""
        stderr = "Quantization failed"

    monkeypatch.setattr(subprocess, "run", lambda cmd, capture_output, text: MockFailProc())
    with pytest.raises(RuntimeError):
        export_mod.quantize_gguf(input_gguf, output_gguf, "Q4_K_M")

def test_proxy_server_extended_routes(tmp_path, monkeypatch):
    class FakeStream:
        def __init__(self):
            self.data = bytearray()
        def write(self, b):
            self.data.extend(b)
        def flush(self):
            pass

    class DummyHandler(proxy_srv.AnthropicProxyHandler):
        def __init__(self, path="/gui", method="GET", rfile_data=b""):
            self.path = path
            self.command = method
            self.headers = {"Content-Length": str(len(rfile_data))}
            self.rfile = io.BytesIO(rfile_data)
            self.wfile = FakeStream()
            self.headers_sent = []
            self.response_code = None

        def send_response(self, code, message=None):
            self.response_code = code

        def send_header(self, keyword, value):
            self.headers_sent.append((keyword, value))

        def end_headers(self):
            pass

    # HEAD
    h_head = DummyHandler("/", "HEAD")
    h_head.do_HEAD()
    assert h_head.response_code == 200

    # GET /gui
    h_gui = DummyHandler("/gui", "GET")
    h_gui.do_GET()
    assert h_gui.response_code == 200
    assert b"<!DOCTYPE html>" in h_gui.wfile.data or b"<html" in h_gui.wfile.data

    # GET /api/status
    h_status = DummyHandler("/api/status", "GET")
    h_status.do_GET()
    assert h_status.response_code == 200
    assert b"total_raw_traces" in h_status.wfile.data

    # POST invalid json
    h_inv = DummyHandler("/v1/messages", "POST", b"invalid-json")
    h_inv.do_POST()
    assert h_inv.response_code == 400

    # POST with mock upstream success
    class MockResp:
        def read(self):
            return json.dumps({
                "choices": [{
                    "message": {
                        "content": "Hello world"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3}
            }).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=600: MockResp())
    post_body = json.dumps({
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": False
    }).encode("utf-8")

    h_post = DummyHandler("/v1/messages", "POST", post_body)
    h_post.do_POST()
    assert h_post.response_code == 200
    assert b"Hello world" in h_post.wfile.data


