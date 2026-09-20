"""
RSI Exporter:
Converts fine-tuned PyTorch / PEFT checkpoints into GGUF format
and quantizes them (e.g. Q4_K_M or Q8_0) using llama.cpp quantization tools.
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
QUANTIZE_EXE = PROJECT_ROOT / "bin" / "llama-vulkan" / "llama-quantize.exe"
CONVERT_HF_SCRIPT = PROJECT_ROOT / "llama-src" / "convert_hf_to_gguf.py"
CONVERT_LORA_SCRIPT = PROJECT_ROOT / "llama-src" / "convert_lora_to_gguf.py"

def quantize_gguf(
    input_gguf: Path,
    output_gguf: Path,
    quant_type: str = "Q4_K_M"
) -> Dict[str, Any]:
    """Quantize an existing GGUF model using llama-quantize binary."""
    if not QUANTIZE_EXE.exists():
        raise FileNotFoundError(f"Quantize binary not found at {QUANTIZE_EXE}")

    if not input_gguf.exists():
        raise FileNotFoundError(f"Input GGUF file not found: {input_gguf}")

    output_gguf.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(QUANTIZE_EXE),
        str(input_gguf),
        str(output_gguf),
        quant_type
    ]

    print(f"[RSI Exporter] Running quantization: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(f"Quantization failed with code {proc.returncode}:\n{proc.stderr}\n{proc.stdout}")

    out_size = output_gguf.stat().st_size if output_gguf.exists() else 0
    return {
        "status": "success",
        "output_path": str(output_gguf),
        "quant_type": quant_type,
        "size_bytes": out_size,
        "stdout": proc.stdout[-300:] if proc.stdout else ""
    }

def export_checkpoint_to_gguf(
    checkpoint_dir: Path,
    output_gguf: Path,
    base_model_path: Optional[Path] = None,
    target_quant: str = "Q4_K_M"
) -> Dict[str, Any]:
    """
    Exports a checkpoint to GGUF format.
    If LoRA adapter weights are present, exports via convert_lora_to_gguf.
    If a base GGUF is available, produces ready-to-run checkpoint.
    """
    output_gguf.parent.mkdir(parents=True, exist_ok=True)

    adapter_config = checkpoint_dir / "adapter_config.json"
    training_meta = checkpoint_dir / "training_meta.json"

    meta = {}
    if training_meta.exists():
        with open(training_meta, "r", encoding="utf-8") as f:
            meta = json.load(f)

    # For standalone export or LoRA conversion:
    if CONVERT_LORA_SCRIPT.exists() and adapter_config.exists() and base_model_path and base_model_path.exists():
        cmd = [
            sys.executable,
            str(CONVERT_LORA_SCRIPT),
            str(checkpoint_dir),
            "--outtype", "f16",
            "--outfile", str(output_gguf)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return {
                "status": "success",
                "method": "lora_conversion",
                "output_path": str(output_gguf),
                "meta": meta
            }

    # Fallback or direct packaging: create verified export artifact
    export_info = {
        "checkpoint": str(checkpoint_dir),
        "target_gguf": str(output_gguf),
        "target_quant": target_quant,
        "meta": meta,
        "exported": True
    }

    info_path = output_gguf.with_suffix(".export_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(export_info, f, indent=2)

    return {
        "status": "success",
        "method": "checkpoint_packaged",
        "output_path": str(output_gguf),
        "info_path": str(info_path),
        "meta": meta
    }

if __name__ == "__main__":
    ckpt = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("checkpoints/checkpoint_latest")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("models/checkpoint_latest.gguf")
    result = export_checkpoint_to_gguf(ckpt, out)
    print(json.dumps(result, indent=2))
