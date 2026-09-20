"""
RSI Curator Pipeline:
Filters raw interaction traces into high-quality training pairs
and creates a temporally-held-out test split.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

def load_raw_traces(raw_dir: Path) -> List[Dict[str, Any]]:
    """Load all raw JSON trace files from raw_dir."""
    traces = []
    if not raw_dir.exists():
        return traces

    for p in sorted(raw_dir.glob("trace_*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                traces.append(data)
        except Exception:
            continue
    return traces

def is_valid_trace(trace: Dict[str, Any]) -> bool:
    """Filter traces to ensure high quality demonstration data."""
    if not trace.get("success", False):
        return False

    req = trace.get("request", {})
    resp = trace.get("response", {})

    # Check request structure
    messages = req.get("messages", [])
    if not messages:
        return False

    # Check response structure
    content = resp.get("content", [])
    if not content:
        return False

    # Ensure response has either valid text or valid tool_use
    has_meaningful_output = False
    for block in content:
        if block.get("type") == "text" and block.get("text", "").strip():
            has_meaningful_output = True
        elif block.get("type") == "tool_use" and block.get("name"):
            has_meaningful_output = True

    return has_meaningful_output

def format_trace_for_training(trace: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw trace into standard instruction-tuning format."""
    req = trace["request"]
    resp = trace["response"]

    # System instruction
    system_prompt = req.get("system", "You are an honest and capable AI coding assistant.")
    if isinstance(system_prompt, list):
        sys_str = "\n".join(b.get("text", "") for b in system_prompt if b.get("type") == "text")
    else:
        sys_str = str(system_prompt)

    # User message
    user_str = ""
    for msg in req.get("messages", []):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                user_str += content + "\n"
            elif isinstance(content, list):
                for b in content:
                    if b.get("type") == "text":
                        user_str += b.get("text", "") + "\n"

    # Assistant response
    assistant_str = ""
    for block in resp.get("content", []):
        if block.get("type") == "text":
            assistant_str += block.get("text", "")
        elif block.get("type") == "tool_use":
            tool_call = {
                "name": block.get("name"),
                "parameters": block.get("input", {})
            }
            assistant_str += f"\n```json\n{json.dumps(tool_call, indent=2)}\n```\n"

    return {
        "timestamp": trace.get("timestamp", 0),
        "instruction": f"<|im_start|>system\n{sys_str}<|im_end|>\n<|im_start|>user\n{user_str.strip()}<|im_end|>\n<|im_start|>assistant\n",
        "response": f"{assistant_str.strip()}<|im_end|>"
    }

def curate_dataset(raw_dir: Path, output_dir: Path, eval_split_ratio: float = 0.2) -> Tuple[int, int]:
    """
    Curate raw traces and output train.jsonl and eval.jsonl.
    Uses temporal split: the most recent `eval_split_ratio` of data becomes eval.
    """
    traces = load_raw_traces(raw_dir)
    valid_traces = [t for t in traces if is_valid_trace(t)]
    # Sort strictly by timestamp
    valid_traces.sort(key=lambda t: t.get("timestamp", 0))

    formatted = [format_trace_for_training(t) for t in valid_traces]

    if not formatted:
        return 0, 0

    output_dir.mkdir(parents=True, exist_ok=True)
    n_total = len(formatted)
    n_eval = max(1, int(n_total * eval_split_ratio)) if n_total > 1 else 0
    n_train = n_total - n_eval

    train_data = formatted[:n_train] if n_train > 0 else formatted
    eval_data = formatted[n_train:] if n_eval > 0 else []

    train_path = output_dir / "train.jsonl"
    eval_path = output_dir / "eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item) + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for item in eval_data:
            f.write(json.dumps(item) + "\n")

    return len(train_data), len(eval_data)
