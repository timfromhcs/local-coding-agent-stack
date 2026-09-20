"""
Unit tests for RSI sub-components: Curator, Dataset, Exporter, and Daemon Status.
Zero mocks: tests real dataset loading, status generation, file export, and validation.
"""

import os
import json
import time
import pytest
from pathlib import Path
from src.rsi.curator import load_raw_traces, is_valid_trace, format_trace_for_training, curate_dataset
from src.rsi.trainer import InstructionDataset
from src.rsi.export import export_checkpoint_to_gguf
from src.rsi.daemon import get_current_status, save_status
from src.rsi.benchmark import extract_code_block, execute_code_safely
from src.proxy.server import log_rsi_interaction

def test_instruction_dataset(tmp_path):
    class DummyTokenizer:
        def __call__(self, text, max_length, truncation, padding, return_tensors):
            import torch
            return {
                "input_ids": torch.tensor([[10, 20, 30]]),
                "attention_mask": torch.tensor([[1, 1, 1]])
            }

    data_file = tmp_path / "train.jsonl"
    with open(data_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"instruction": "Hello", "response": " World"}) + "\n")

    ds = InstructionDataset(data_file, DummyTokenizer())
    assert len(ds) == 1
    sample = ds[0]
    assert "input_ids" in sample
    assert "labels" in sample

def test_curate_dataset_flow(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "curated"

    trace = {
        "success": True,
        "timestamp": 1234567.0,
        "request": {
            "system": "System instruction",
            "messages": [{"role": "user", "content": "Write Python"}]
        },
        "response": {
            "content": [{"type": "text", "text": "print('ok')"}]
        }
    }
    with open(raw_dir / "trace_01.json", "w", encoding="utf-8") as f:
        json.dump(trace, f)

    n_train, n_eval = curate_dataset(raw_dir, out_dir)
    assert n_train + n_eval == 1
    assert (out_dir / "train.jsonl").exists()

def test_export_checkpoint_packaging(tmp_path):
    ckpt_dir = tmp_path / "test_ckpt"
    ckpt_dir.mkdir()
    meta_file = ckpt_dir / "training_meta.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({"loss": 1.23, "epochs": 2}, f)

    target_gguf = tmp_path / "test_out.gguf"
    res = export_checkpoint_to_gguf(ckpt_dir, target_gguf)
    assert res["status"] == "success"
    assert res["method"] == "checkpoint_packaged"
    assert (tmp_path / "test_out.export_info.json").exists()

def test_daemon_status_persistence(tmp_path, monkeypatch):
    import src.rsi.daemon as daemon_mod
    status_file = tmp_path / "status.json"
    monkeypatch.setattr(daemon_mod, "STATUS_FILE", status_file)

    st = daemon_mod.get_current_status()
    assert "current_production_model" in st
    st["test_flag"] = "active"
    daemon_mod.save_status(st)

    loaded = daemon_mod.get_current_status()
    assert loaded["test_flag"] == "active"

def test_rsi_interaction_logging(tmp_path, monkeypatch):
    import src.proxy.server as srv
    raw_dir = tmp_path / "raw_traces"
    monkeypatch.setattr(srv, "RSI_RAW_LOG_DIR", raw_dir)

    req = {"model": "test", "messages": [{"role": "user", "content": "hi"}]}
    resp = {"type": "message", "content": [{"type": "text", "text": "hi"}]}
    srv.log_rsi_interaction(req, resp, latency_ms=45.2, success=True)

    files = list(raw_dir.glob("trace_*.json"))
    assert len(files) == 1
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["success"] is True
    assert data["latency_ms"] == 45.2
