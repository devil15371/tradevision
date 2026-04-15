"""
Phase 4 Benchmark — Test fine-tuned Qwen2-VL against unseen documents.
Determines if model learned to generalize or just memorized training data.

Run: python3 training/benchmark.py
"""

from unsloth import FastVisionModel
from transformers import AutoProcessor
import torch
import fitz
import json
import os

BASE_MODEL_ID = "unsloth/qwen2-vl-7b-instruct-unsloth-bnb-4bit"
FINETUNED_PATH = "models/tradevision_finetuned"

os.makedirs("outputs/benchmark", exist_ok=True)


def load_model(path, label="model"):
    print(f"Loading {label} from {path}...")
    model, tokenizer = FastVisionModel.from_pretrained(
        path,
        load_in_4bit=True,
    )
    FastVisionModel.for_inference(model)
    processor = AutoProcessor.from_pretrained(path)
    print(f"{label} loaded.\n")
    return model, tokenizer, processor


def pdf_to_image(pdf_path, out_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    pix.save(out_path)
    doc.close()
    return out_path


def run_inference(model, processor, invoice_path, packing_list_path, tag="test"):
    inv_img = pdf_to_image(invoice_path, f"outputs/benchmark/inv_{tag}.png")
    pl_img  = pdf_to_image(packing_list_path, f"outputs/benchmark/pl_{tag}.png")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text",  "text": (
                    "You are a customs compliance auditor for Indian exports. "
                    "Compare the commercial invoice and packing list images. "
                    "Check for gross weight mismatches and HS code mismatches. "
                    "Return ONLY a JSON object with keys: status (PASSED or REJECTED), "
                    "issues (list), summary (string)."
                )},
                {"type": "text",  "text": "COMMERCIAL INVOICE:"},
                {"type": "image", "image": f"file://{os.path.abspath(inv_img)}"},
                {"type": "text",  "text": "PACKING LIST:"},
                {"type": "image", "image": f"file://{os.path.abspath(pl_img)}"},
            ]
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    from qwen_vl_utils import process_vision_info
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt"
    ).to("cuda")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.1,
            do_sample=False,
        )

    raw = processor.batch_decode(
        output_ids[:, inputs.input_ids.shape[1]:],
        skip_special_tokens=True
    )[0]

    try:
        start = raw.find('{')
        end   = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass
    return {"raw_output": raw, "parse_error": True}


def score(result, expected_status):
    if "parse_error" in result:
        return False
    return result.get("status") == expected_status


TEST_CASES = [
    {
        "label":    "Correct docs (expect PASSED)",
        "invoice":  "data/invoice_1_correct.pdf",
        "pl":       "data/packing_list_1_correct.pdf",
        "expected": "PASSED",
        "tag":      "correct",
    },
    {
        "label":    "Error docs (expect REJECTED)",
        "invoice":  "data/invoice_2_errors.pdf",
        "pl":       "data/packing_list_2_errors.pdf",
        "expected": "REJECTED",
        "tag":      "errors",
    },
]


def run_benchmark(model, processor, model_label):
    print(f"\n{'='*55}")
    print(f"  {model_label}")
    print(f"{'='*55}")
    results = []
    for tc in TEST_CASES:
        print(f"\n[{tc['label']}]")
        result = run_inference(model, processor, tc["invoice"], tc["pl"], tc["tag"])
        ok = score(result, tc["expected"])
        print(json.dumps(result, indent=2))
        print(f"→ {'✅ CORRECT' if ok else '❌ WRONG'} (expected {tc['expected']})")
        results.append(ok)
    print(f"\nScore: {sum(results)}/{len(results)}")
    return results


if __name__ == "__main__":
    # ── Fine-tuned model ──────────────────────────────────────────
    ft_model, ft_tok, ft_proc = load_model(FINETUNED_PATH, "Fine-tuned TradeVision")
    ft_scores = run_benchmark(ft_model, ft_proc, "FINE-TUNED MODEL")

    # Free GPU memory before loading base model
    del ft_model, ft_tok, ft_proc
    torch.cuda.empty_cache()

    # ── Base model (no fine-tuning) ───────────────────────────────
    base_model, base_tok, base_proc = load_model(BASE_MODEL_ID, "Base Qwen2-VL-7B")
    base_scores = run_benchmark(base_model, base_proc, "BASE MODEL (no fine-tuning)")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  FINAL COMPARISON")
    print(f"{'='*55}")
    print(f"  Fine-tuned : {sum(ft_scores)}/{len(ft_scores)}")
    print(f"  Base model : {sum(base_scores)}/{len(base_scores)}")
    if sum(ft_scores) > sum(base_scores):
        print(f"\n  ✅ Fine-tuning HELPED — model improved!")
    elif sum(ft_scores) == sum(base_scores):
        print(f"\n  ⚠️  Same score — need more training data or epochs")
    else:
        print(f"\n  ❌ Fine-tuned did WORSE — likely overfit")
