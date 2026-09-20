"""
Unit tests for RSI modules: Curator, Benchmark, and Promoter.
Zero mocks: tests validation rules, scoring logic, and execution sandboxing.
"""

import pytest
import json
from pathlib import Path
from src.rsi.curator import is_valid_trace, format_trace_for_training, curate_dataset
from src.rsi.promoter import evaluate_promotion
from src.rsi.benchmark import extract_code_block, execute_code_safely

def test_curator_valid_trace():
    valid = {
        "success": True,
        "timestamp": 123456,
        "request": {
            "system": "System instruction",
            "messages": [{"role": "user", "content": "How do I print in Python?"}]
        },
        "response": {
            "content": [{"type": "text", "text": "print('hello')"}]
        }
    }
    assert is_valid_trace(valid) is True

def test_curator_invalid_trace():
    failed = {
        "success": False,
        "request": {"messages": [{"role": "user", "content": "hi"}]},
        "response": {"content": [{"type": "text", "text": "hi"}]}
    }
    assert is_valid_trace(failed) is False

    empty_resp = {
        "success": True,
        "request": {"messages": [{"role": "user", "content": "hi"}]},
        "response": {"content": []}
    }
    assert is_valid_trace(empty_resp) is False

def test_curator_format_trace():
    trace = {
        "success": True,
        "timestamp": 1000,
        "request": {
            "system": "Be concise.",
            "messages": [{"role": "user", "content": "What is 2+2?"}]
        },
        "response": {
            "content": [{"type": "text", "text": "4"}]
        }
    }
    fmt = format_trace_for_training(trace)
    assert "<|im_start|>system\nBe concise.<|im_end|>" in fmt["instruction"]
    assert "<|im_start|>user\nWhat is 2+2?<|im_end|>" in fmt["instruction"]
    assert fmt["response"] == "4<|im_end|>"

def test_benchmark_code_extraction():
    md = """Here is the code:
```python
def add(a, b):
    return a + b
```
Enjoy!"""
    code = extract_code_block(md)
    assert code == "def add(a, b):\n    return a + b"

def test_benchmark_execution_sandbox():
    code = "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)"
    ok, res = execute_code_safely(code, "fib", [6])
    assert ok is True
    assert res == 8

    # Syntax error handling
    bad_code = "def broken(:"
    ok, err = execute_code_safely(bad_code, "broken", [])
    assert ok is False

def test_promoter_gate_logic():
    # Scenario 1: strictly higher pass rate, no regressions, latency OK -> PROMOTED
    cand_good = {
        "pass_rate": 0.90,
        "mean_latency_ms": 105.0,
        "task_results": [{"task_id": "t1", "passed": True}, {"task_id": "t2", "passed": True}]
    }
    prod_good = {
        "pass_rate": 0.80,
        "mean_latency_ms": 100.0,
        "task_results": [{"task_id": "t1", "passed": True}, {"task_id": "t2", "passed": False}]
    }
    passed, reasons = evaluate_promotion(cand_good, prod_good)
    assert passed is True
    assert len(reasons) == 0

    # Scenario 2: equal pass rate -> REJECTED (must be strictly higher)
    cand_equal = dict(cand_good, pass_rate=0.80)
    passed, reasons = evaluate_promotion(cand_equal, prod_good)
    assert passed is False
    assert any("not strictly higher" in r for r in reasons)

    # Scenario 3: regression on core task -> REJECTED
    cand_regr = {
        "pass_rate": 0.85,
        "mean_latency_ms": 100.0,
        "task_results": [{"task_id": "t1", "passed": False}, {"task_id": "t2", "passed": True}]
    }
    passed, reasons = evaluate_promotion(cand_regr, prod_good)
    assert passed is False
    assert any("Regressions detected" in r for r in reasons)

    # Scenario 4: latency regression > 10% -> REJECTED
    cand_slow = dict(cand_good, mean_latency_ms=125.0)
    passed, reasons = evaluate_promotion(cand_slow, prod_good)
    assert passed is False
    assert any("Latency regression exceeded 10%" in r for r in reasons)
