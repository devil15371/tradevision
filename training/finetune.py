"""
Phase 3 — Fine-tune Qwen2-VL-7B-Instruct on TradeVision dataset using Unsloth + LoRA.

Run inside tmux:
    tmux new -s training
    source venv/bin/activate
    python3 training/finetune.py
"""

import torch
import os

os.environ["HF_HUB_DISABLE_XET_TRANSPORT"] = "1"  # avoid xet protocol issues


def main():
    # ── 1. Load base model ────────────────────────────────────────
    print("[1/5] Loading base model...")
    from unsloth import FastVisionModel

    model, tokenizer = FastVisionModel.from_pretrained(
        "Qwen/Qwen2-VL-7B-Instruct",
        load_in_4bit=True,                        # 4-bit quant saves ~50% VRAM
        use_gradient_checkpointing="unsloth",     # reduces VRAM further
    )

    # ── 2. Add LoRA adapters ──────────────────────────────────────
    print("[2/5] Adding LoRA adapters...")
    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers=True,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=16,
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        random_state=42,
    )

    # ── 3. Load dataset ───────────────────────────────────────────
    print("[3/5] Loading dataset...")
    from datasets import load_dataset

    dataset = load_dataset(
        "json",
        data_files="training/dataset.jsonl",
        split="train"
    )
    print(f"  Dataset size: {len(dataset)} samples")

    # ── 4. Build trainer ──────────────────────────────────────────
    print("[4/5] Setting up trainer...")
    from trl import SFTTrainer, SFTConfig
    from unsloth.trainer import UnslothVisionDataCollator

    use_bf16 = torch.cuda.is_bf16_supported()

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        data_collator=UnslothVisionDataCollator(model, tokenizer),
        train_dataset=dataset,
        args=SFTConfig(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,   # effective batch = 8
            warmup_steps=10,
            num_train_epochs=3,
            learning_rate=2e-4,
            fp16=not use_bf16,
            bf16=use_bf16,
            logging_steps=10,
            optim="adamw_8bit",
            output_dir="models/checkpoints",
            report_to="none",
            remove_unused_columns=False,
            dataset_text_field="",
            dataset_kwargs={"skip_prepare_dataset": True},
            max_seq_length=2048,
            save_steps=100,
            save_total_limit=3,             # keep only 3 checkpoints
        ),
    )

    # ── 5. Train ──────────────────────────────────────────────────
    print("[5/5] Starting training... (this will take 2-4 hours on H100)")
    print("  Monitor loss with: tail -f training/training.log")

    trainer_stats = trainer.train()

    # ── Save final model ──────────────────────────────────────────
    save_path = "models/tradevision_finetuned"
    model.save_pretrained(save_path)
    tokenizer.save_pretrained(save_path)

    print(f"\nTraining complete!")
    print(f"  Model saved to: {save_path}")
    print(f"  Final loss: {trainer_stats.training_loss:.4f}")
    print(f"  Time taken: {trainer_stats.metrics.get('train_runtime', 0)/3600:.2f} hours")


if __name__ == "__main__":
    main()
