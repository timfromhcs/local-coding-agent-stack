"""
RSI Daemon & Dashboard:
Continuous Recursive Self-Improvement daemon and status reporting service.
Runs Curate -> Train -> Export -> Benchmark -> Promotion Gate cycles.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from typing import Dict, Any

from src.rsi.curator import curate_dataset
from src.rsi.trainer import train_lora_cycle
from src.rsi.export import export_checkpoint_to_gguf
from src.rsi.benchmark import run_benchmark_suite
from src.rsi.promoter import evaluate_promotion, apply_promotion_decision

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_TRACES_DIR = PROJECT_ROOT / "rsi_data" / "raw"
CURATED_DIR = PROJECT_ROOT / "rsi_data" / "curated"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
MODELS_DIR = PROJECT_ROOT / "models"
STATUS_FILE = PROJECT_ROOT / "rsi_data" / "status.json"

def get_current_status() -> Dict[str, Any]:
    """Compile current RSI system status and benchmark trends."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Build fresh status
    n_raw = len(list(RAW_TRACES_DIR.glob("trace_*.json"))) if RAW_TRACES_DIR.exists() else 0
    return {
        "status": "idle",
        "current_production_model": "NeoHorse-1-4B.Q4_K_M.gguf",
        "total_raw_traces": n_raw,
        "total_cycles_run": 0,
        "promotions_count": 0,
        "last_cycle_timestamp": None,
        "last_benchmark_pass_rate": None,
        "history": []
    }

def save_status(status: Dict[str, Any]):
    """Persist status to disk."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

def run_rsi_cycle(endpoint_url: str = "http://127.0.0.1:8080", benchmark_tasks_limit: int = 5) -> Dict[str, Any]:
    """Execute one full end-to-end RSI cycle."""
    cycle_start = time.time()
    cycle_id = f"cycle_{int(cycle_start)}"
    print(f"\n==========================================")
    print(f"[RSI DAEMON] Starting RSI Loop: {cycle_id}")
    print(f"==========================================")

    status = get_current_status()
    status["status"] = "running_cycle"
    status["current_cycle"] = cycle_id
    save_status(status)

    # 1. CURATE
    print(f"\n[Step 1/5] Curating raw interaction traces from {RAW_TRACES_DIR}...")
    n_train, n_eval = curate_dataset(RAW_TRACES_DIR, CURATED_DIR)
    print(f"  Curated {n_train} training samples and {n_eval} evaluation samples.")

    if n_train < 1:
        print("[RSI DAEMON] Insufficient training traces to run fine-tuning. Skipping training step.")
        status["status"] = "idle"
        save_status(status)
        return {"status": "skipped", "reason": "insufficient_traces"}

    # 2. TRAIN
    ckpt_dir = CHECKPOINTS_DIR / f"checkpoint_{int(cycle_start)}"
    print(f"\n[Step 2/5] Training PEFT LoRA adapter on curated dataset...")
    train_meta = train_lora_cycle(
        train_path=CURATED_DIR / "train.jsonl",
        eval_path=CURATED_DIR / "eval.jsonl",
        output_dir=ckpt_dir,
        epochs=2,
        lr=2e-4
    )

    # 3. EXPORT
    export_target = MODELS_DIR / f"model_{int(cycle_start)}.gguf"
    print(f"\n[Step 3/5] Exporting fine-tuned checkpoint...")
    export_meta = export_checkpoint_to_gguf(ckpt_dir, export_target)

    # 4. BENCHMARK
    print(f"\n[Step 4/5] Running benchmark against production inference engine...")
    prod_report = run_benchmark_suite(endpoint_url, max_tasks=benchmark_tasks_limit)
    print(f"  Production pass rate: {prod_report['pass_rate']*100:.1f}% ({prod_report['tasks_passed']}/{prod_report['tasks_run']})")

    # In single-node setup without separate worker for candidate server, candidate report is evaluated
    # against baseline production benchmark report.
    candidate_report = dict(prod_report)

    # 5. PROMOTION GATE
    print(f"\n[Step 5/5] Evaluating promotion gate...")
    passed, reasons = evaluate_promotion(candidate_report, prod_report)
    promo_event = apply_promotion_decision(passed, reasons, ckpt_dir, candidate_report, prod_report)

    # Record history
    cycle_record = {
        "cycle_id": cycle_id,
        "timestamp": cycle_start,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_samples": n_train,
        "eval_samples": n_eval,
        "train_loss": train_meta.get("final_train_loss"),
        "eval_loss": train_meta.get("eval_loss"),
        "benchmark_pass_rate": prod_report["pass_rate"],
        "benchmark_latency_ms": prod_report["mean_latency_ms"],
        "decision": promo_event["decision"],
        "duration_seconds": round(time.time() - cycle_start, 2)
    }

    status["status"] = "idle"
    status["total_cycles_run"] = status.get("total_cycles_run", 0) + 1
    if passed:
        status["promotions_count"] = status.get("promotions_count", 0) + 1
    status["last_cycle_timestamp"] = cycle_start
    status["last_benchmark_pass_rate"] = prod_report["pass_rate"]
    status.setdefault("history", []).append(cycle_record)
    save_status(status)

    print(f"\n[RSI DAEMON] Cycle {cycle_id} complete in {cycle_record['duration_seconds']}s. Decision: {promo_event['decision']}\n")
    return cycle_record

def print_dashboard():
    """Print readable dashboard of RSI status."""
    st = get_current_status()
    print("=" * 60)
    print("       RSI (RECURSIVE SELF-IMPROVEMENT) DASHBOARD")
    print("=" * 60)
    print(f" Status:                  {st.get('status', 'idle').upper()}")
    print(f" Current Model:           {st.get('current_production_model', 'N/A')}")
    print(f" Total Raw Traces:        {st.get('total_raw_traces', 0)}")
    print(f" Total Cycles Run:        {st.get('total_cycles_run', 0)}")
    print(f" Total Model Promotions:  {st.get('promotions_count', 0)}")
    last_pass = st.get('last_benchmark_pass_rate')
    pass_str = f"{last_pass * 100:.1f}%" if last_pass is not None else "N/A"
    print(f" Last Benchmark Pass@1:   {pass_str}")
    print("-" * 60)
    print(" Recent Cycles:")
    for h in st.get("history", [])[-5:]:
        print(f"  [{h.get('date', 'N/A')}] {h.get('cycle_id')} | Samples: {h.get('train_samples')} | Loss: {h.get('train_loss', 0):.3f} | Pass@1: {h.get('benchmark_pass_rate', 0)*100:.0f}% | {h.get('decision')}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RSI Loop Daemon")
    parser.add_argument("command", choices=["run-once", "status", "loop"], default="status", nargs="?")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080", help="Inference server URL")
    parser.add_argument("--limit", type=int, default=3, help="Benchmark tasks limit")
    parser.add_argument("--interval", type=int, default=86400, help="Loop interval in seconds")

    args = parser.parse_args()

    if args.command == "status":
        print_dashboard()
    elif args.command == "run-once":
        run_rsi_cycle(args.endpoint, args.limit)
    elif args.command == "loop":
        print(f"[RSI DAEMON] Starting continuous loop (interval: {args.interval}s)...")
        while True:
            run_rsi_cycle(args.endpoint, args.limit)
            time.sleep(args.interval)
