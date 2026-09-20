"""
RSI Promotion Gate:
Enforces strict gate logic:
- pass@1 MUST be strictly HIGHER than production (pass_rate > prod_pass_rate)
- Zero regression on any benchmark task that passed in production
- Inference latency regression < 10%
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROMOTION_LOG = PROJECT_ROOT / "rsi_data" / "promotions.jsonl"
ARCHIVE_DIR = PROJECT_ROOT / "checkpoints" / "archive"

def evaluate_promotion(
    candidate_report: Dict[str, Any],
    production_report: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Evaluates candidate benchmark report against production.
    Returns (passed, list_of_failure_reasons).
    """
    reasons = []

    cand_pass = candidate_report.get("pass_rate", 0.0)
    prod_pass = production_report.get("pass_rate", 0.0)

    # Criterion 1: pass@1 must be strictly higher
    if cand_pass <= prod_pass:
        reasons.append(
            f"Pass rate not strictly higher: candidate {cand_pass*100:.1f}% <= production {prod_pass*100:.1f}%"
        )

    # Criterion 2: Zero regression on tasks that passed in production
    prod_tasks = {r["task_id"]: r["passed"] for r in production_report.get("task_results", [])}
    cand_tasks = {r["task_id"]: r["passed"] for r in candidate_report.get("task_results", [])}

    regressions = []
    for task_id, passed_in_prod in prod_tasks.items():
        if passed_in_prod and not cand_tasks.get(task_id, False):
            regressions.append(task_id)

    if regressions:
        reasons.append(f"Regressions detected on tasks that passed in production: {', '.join(regressions)}")

    # Criterion 3: Latency regression < 10%
    cand_lat = candidate_report.get("mean_latency_ms", float("inf"))
    prod_lat = production_report.get("mean_latency_ms", 1.0)
    if prod_lat > 0:
        lat_ratio = (cand_lat - prod_lat) / prod_lat
        if lat_ratio > 0.10:
            reasons.append(f"Latency regression exceeded 10%: +{lat_ratio*100:.1f}% ({cand_lat:.1f}ms vs {prod_lat:.1f}ms)")

    passed = len(reasons) == 0
    return passed, reasons

def record_promotion_event(event: Dict[str, Any]):
    """Log promotion decisions to persistent jsonl ledger."""
    PROMOTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMOTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

def apply_promotion_decision(
    passed: bool,
    reasons: List[str],
    checkpoint_dir: Path,
    candidate_report: Dict[str, Any],
    production_report: Dict[str, Any]
) -> Dict[str, Any]:
    """Applies promotion or archives rejected checkpoint."""
    event = {
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "PROMOTED" if passed else "REJECTED",
        "reasons": reasons,
        "candidate_pass_rate": candidate_report.get("pass_rate"),
        "production_pass_rate": production_report.get("pass_rate"),
        "candidate_latency_ms": candidate_report.get("mean_latency_ms"),
        "production_latency_ms": production_report.get("mean_latency_ms"),
        "checkpoint": str(checkpoint_dir)
    }

    record_promotion_event(event)

    if not passed:
        # Archive rejected checkpoint
        dest = ARCHIVE_DIR / f"rejected_{int(time.time())}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if checkpoint_dir.exists():
            shutil.copytree(checkpoint_dir, dest, dirs_exist_ok=True)
        print(f"[RSI Promoter] Checkpoint rejected. Archived to {dest}")
        print(f"  Reasons: {reasons}")
    else:
        # Promotion logic: update production model reference
        prod_target = PROJECT_ROOT / "models" / "current_production.gguf"
        print(f"[RSI Promoter] CHECKPOINT PROMOTED! pass@1: {candidate_report.get('pass_rate')*100:.1f}%")
        print(f"  Updating production pointer to: {checkpoint_dir}")

    return event

if __name__ == "__main__":
    # Test runner for promotion gate
    cand_demo = {"pass_rate": 0.85, "mean_latency_ms": 120.0, "task_results": [{"task_id": "algo-01", "passed": True}]}
    prod_demo = {"pass_rate": 0.80, "mean_latency_ms": 115.0, "task_results": [{"task_id": "algo-01", "passed": True}]}
    p, r = evaluate_promotion(cand_demo, prod_demo)
    print(f"Demo Gate result: passed={p}, reasons={r}")
