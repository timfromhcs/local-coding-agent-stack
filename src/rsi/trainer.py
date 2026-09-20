"""
RSI Trainer Pipeline:
Fine-tunes model weights / LoRA adapters using PyTorch and PEFT on curated traces.
Saves checkpoints with loss metrics, timestamps, and adapter weights.
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoConfig, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

class InstructionDataset(Dataset):
    def __init__(self, data_path: Path, tokenizer, max_length: int = 512):
        self.samples = []
        self.tokenizer = tokenizer
        self.max_length = max_length

        if not data_path.exists():
            return

        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                full_text = item["instruction"] + item["response"]
                self.samples.append(full_text)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        text = self.samples[idx]
        enc = self.tokenizer(
            text,
            max_length=self.max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt"
        )
        input_ids = enc["input_ids"].squeeze(0)
        attention_mask = enc["attention_mask"].squeeze(0)
        labels = input_ids.clone()
        # Mask padding tokens in loss calculation
        labels[attention_mask == 0] = -100
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels
        }

def train_lora_cycle(
    train_path: Path,
    eval_path: Path,
    output_dir: Path,
    base_model_name_or_path: Optional[str] = None,
    epochs: int = 3,
    lr: float = 2e-4,
    batch_size: int = 2,
    lora_r: int = 8,
    lora_alpha: int = 16,
    device: str = "cpu"
) -> Dict[str, Any]:
    """
    Run full LoRA training cycle using PyTorch and PEFT.
    Logs loss per step and returns summary metrics.
    """
    t_start = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[RSI Trainer] Initializing LoRA training on device: {device}...")

    # Load or initialize model and tokenizer
    tokenizer = None
    model = None

    if base_model_name_or_path and Path(base_model_name_or_path).exists():
        try:
            tokenizer = AutoTokenizer.from_pretrained(base_model_name_or_path, local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(base_model_name_or_path, local_files_only=True)
        except Exception as e:
            print(f"[RSI Trainer] Could not load local base model {base_model_name_or_path}: {e}")

    if tokenizer is None:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        tokenizer.pad_token = tokenizer.eos_token

    if model is None:
        from transformers import GPT2Config, GPT2LMHeadModel
        vocab_size = max(len(tokenizer), 50257)
        config = GPT2Config(
            vocab_size=vocab_size,
            n_positions=512,
            n_embd=256,
            n_layer=4,
            n_head=4,
            bos_token_id=tokenizer.bos_token_id or 50256,
            eos_token_id=tokenizer.eos_token_id or 50256,
            pad_token_id=tokenizer.pad_token_id or 50256,
        )
        model = GPT2LMHeadModel(config)

    # Setup PEFT LoRA
    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )

    try:
        peft_model = get_peft_model(model, lora_config)
        peft_model.print_trainable_parameters()
    except Exception as e:
        print(f"[RSI Trainer] PEFT wrapping warning: {e}, falling back to direct parameter training")
        peft_model = model

    peft_model.to(device)

    # Datasets
    train_dataset = InstructionDataset(train_path, tokenizer)
    eval_dataset = InstructionDataset(eval_path, tokenizer)

    if len(train_dataset) == 0:
        raise ValueError(f"No valid training samples found in {train_path}")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    eval_loader = DataLoader(eval_dataset, batch_size=batch_size, shuffle=False) if len(eval_dataset) > 0 else None

    optimizer = torch.optim.AdamW(peft_model.parameters(), lr=lr)

    history = []
    peft_model.train()

    print(f"[RSI Trainer] Training for {epochs} epochs ({len(train_dataset)} samples)...")
    for epoch in range(epochs):
        epoch_loss = 0.0
        steps = 0
        for batch in train_loader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = peft_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            loss = outputs.loss
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            steps += 1

        avg_train_loss = epoch_loss / max(steps, 1)
        print(f"  Epoch {epoch + 1}/{epochs} | Train Loss: {avg_train_loss:.4f}")
        history.append({"epoch": epoch + 1, "train_loss": avg_train_loss})

    # Evaluate
    eval_loss = None
    if eval_loader:
        peft_model.eval()
        total_eval_loss = 0.0
        eval_steps = 0
        with torch.no_grad():
            for batch in eval_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                outputs = peft_model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                total_eval_loss += outputs.loss.item()
                eval_steps += 1
        eval_loss = total_eval_loss / max(eval_steps, 1)
        print(f"[RSI Trainer] Eval Loss: {eval_loss:.4f}")

    duration = time.time() - t_start

    # Save checkpoint
    try:
        peft_model.save_pretrained(str(output_dir))
    except Exception:
        torch.save(peft_model.state_dict(), output_dir / "adapter_model.bin")

    meta = {
        "timestamp": time.time(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epochs": epochs,
        "lr": lr,
        "train_samples": len(train_dataset),
        "eval_samples": len(eval_dataset),
        "final_train_loss": history[-1]["train_loss"] if history else None,
        "eval_loss": eval_loss,
        "duration_seconds": round(duration, 2),
        "device": device,
        "history": history
    }

    with open(output_dir / "training_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"[RSI Trainer] Checkpoint saved successfully to {output_dir} in {duration:.1f}s")
    return meta

if __name__ == "__main__":
    train_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("rsi_data/curated/train.jsonl")
    eval_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("rsi_data/curated/eval.jsonl")
    out_dir = Path("checkpoints/checkpoint_latest")
    train_lora_cycle(train_file, eval_file, out_dir, epochs=2)
