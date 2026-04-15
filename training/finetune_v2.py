"""
Phase 3 V2 Fine-tuning — Qwen2-VL-7B with proper anti-overfit measures:
- 2000 diverse training pairs (4 templates, 15 products, scan noise)
- Train/val 90/10 split
- LoRA rank 32 + dropout 0.05
- Eval every 100 steps — early stopping on val loss

Run inside tmux:
    tmux new -s train_v2
    source venv/bin/activate
    python3 training/finetune_v2.py 2>&1 | tee logs/finetune_v2.log
"""

import json
import random
import os
import io
import torch

os.environ["HF_HUB_DISABLE_XET_TRANSPORT"] = "1"


def ensure_png(pdf_path: str) -> str:
    """Return PNG path — convert from PDF if PNG doesn't exist yet."""
    png_path = pdf_path.replace(".pdf", ".png")
    if os.path.exists(png_path):
        return png_path
    # Convert PDF page 0 to PNG and cache it
    import fitz
    from PIL import Image
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    img.save(png_path)
    return png_path


def build_sample(label: dict) -> dict:
    errors   = label["errors"]
    expected = label["expected_status"]

    if expected == "PASSED":
        out = json.dumps({"status": "PASSED", "issues": [],
                          "summary": "Documents match. No compliance issues detected."})
    else:
        issues = []
        for e in errors:
            if e["type"] == "WEIGHT_MISMATCH":
                diff = round(abs(e["packing_weight"] - e["invoice_weight"]), 2)
                issues.append({"type": "WEIGHT_MISMATCH", "severity": "HIGH",
                                "detail": f"Invoice {e['invoice_weight']}kg vs packing list {e['packing_weight']}kg (diff {diff}kg)"})
            elif e["type"] == "HS_CODE_MISMATCH":
                issues.append({"type": "HS_CODE_MISMATCH", "severity": "HIGH",
                                "detail": f"Invoice HS {e['invoice_hs']} vs packing list HS {e['packing_hs']}"})
        out = json.dumps({"status": "REJECTED", "issues": issues,
                          "summary": f"Found {len(issues)} compliance issue(s)."})

    # Ensure PNGs exist for all docs (PIL can't open PDFs directly)
    inv_url = "file://" + os.path.abspath(ensure_png(label["invoice_path"]))
    pl_url  = "file://" + os.path.abspath(ensure_png(label["packing_list_path"]))

    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text",  "text": (
                        "You are a customs compliance auditor. "
                        "Compare the commercial invoice and packing list. "
                        "Check for weight mismatches and HS code mismatches. "
                        "Return ONLY valid JSON with keys: status, issues, summary."
                    )},
                    {"type": "image", "image": inv_url},
                    {"type": "image", "image": pl_url},
                ]
            },
            {"role": "assistant", "content": out}
        ]
    }


# ── 1. Load base model ─────────────────────────────────────────────
print("[1/6] Loading Qwen2-VL-7B...")
from unsloth import FastVisionModel

model, tokenizer = FastVisionModel.from_pretrained(
    "unsloth/qwen2-vl-7b-instruct-unsloth-bnb-4bit",
    load_in_4bit=True,
    use_gradient_checkpointing="unsloth",
)

# ── 2. LoRA — rank 32, dropout 0.05 ───────────────────────────────
print("[2/6] Adding LoRA adapters (r=32, dropout=0.05)...")
model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers=True,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=32,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    random_state=42,
)

# ── 3. Load & split labels ─────────────────────────────────────────
print("[3/6] Loading labels and splitting 90/10 train/val...")
with open("data/training_v2/labels.json") as f:
    labels = json.load(f)

random.seed(42)
random.shuffle(labels)
split       = int(len(labels) * 0.90)
train_lbl   = labels[:split]
val_lbl     = labels[split:]
print(f"  Train: {len(train_lbl)} | Val: {len(val_lbl)}")

# ── 4. Build datasets ──────────────────────────────────────────────
print("[4/6] Building training samples (this takes a few minutes)...")
from datasets import Dataset

def _build_list(lbls, tag):
    out, skipped = [], 0
    for i, l in enumerate(lbls):
        try:
            out.append(build_sample(l))
        except Exception as e:
            skipped += 1
        if (i + 1) % 200 == 0:
            print(f"  {tag}: {i+1}/{len(lbls)} built  ({skipped} skipped)")
    print(f"  {tag} done: {len(out)} samples ({skipped} skipped)")
    return out

train_samples = _build_list(train_lbl, "TRAIN")
val_samples   = _build_list(val_lbl,   "VAL")

# Pass lists directly — avoids PyArrow serialization of nested image structs
train_ds = train_samples
val_ds   = val_samples

# ── 5. Trainer ─────────────────────────────────────────────────────
print("[5/6] Setting up trainer...")
from trl import SFTTrainer, SFTConfig
from unsloth.trainer import UnslothVisionDataCollator

use_bf16 = torch.cuda.is_bf16_supported()

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    data_collator=UnslothVisionDataCollator(model, tokenizer),
    train_dataset=train_ds,
    eval_dataset=val_ds,
    args=SFTConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,    # effective batch = 16
        warmup_steps=50,
        num_train_epochs=5,
        learning_rate=1e-4,
        fp16=not use_bf16,
        bf16=use_bf16,
        logging_steps=25,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        optim="adamw_8bit",
        output_dir="models/checkpoints_v2",
        report_to="none",
        remove_unused_columns=False,
        dataset_text_field="",
        dataset_kwargs={"skip_prepare_dataset": True},
        max_seq_length=2048,
        seed=42,
        save_total_limit=3,
    ),
)

# ── 6. Train ───────────────────────────────────────────────────────
print("[6/6] Starting training — watch train_loss vs eval_loss.")
print("  Good: both dropping together")
print("  Bad:  eval_loss rising while train_loss drops → overfitting\n")

stats = trainer.train()

# Save best checkpoint
save_path = "models/tradevision_v2"
model.save_pretrained(save_path)
tokenizer.save_pretrained(save_path)

print(f"\n✅ Training complete!")
print(f"  Final train loss : {stats.training_loss:.4f}")
print(f"  Runtime          : {stats.metrics.get('train_runtime', 0)/60:.1f} min")
print(f"  Model saved to   : {save_path}")
