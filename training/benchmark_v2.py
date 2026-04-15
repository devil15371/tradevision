"""
Benchmark V2 — Phase 3 Evaluation
Tests base Qwen2-VL-7B against 50 OOD documents it has never seen.

Run:
    source venv/bin/activate
    python3 training/benchmark_v2.py 2>&1 | tee logs/benchmark_v2.log

Outputs:
    outputs/benchmark_v2_results.json   — full per-sample results
    Terminal summary with accuracy, precision, recall
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import fitz
from PIL import Image

os.makedirs("outputs/benchmark", exist_ok=True)


# ── PDF helpers ────────────────────────────────────────────────────

def pdf_to_pil(pdf_path: str, scale: float = 2.0):
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


# ── Metrics ────────────────────────────────────────────────────────

def compute_metrics(results: list[dict]) -> dict:
    """Compute accuracy, precision, recall for REJECTED class."""
    tp = fp = tn = fn = 0
    for r in results:
        pred   = r["predicted_status"]
        actual = r["expected_status"]
        if actual == "REJECTED" and pred == "REJECTED": tp += 1
        elif actual == "PASSED"  and pred == "REJECTED": fp += 1
        elif actual == "PASSED"  and pred == "PASSED":   tn += 1
        elif actual == "REJECTED" and pred != "REJECTED": fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    accuracy  = (tp + tn) / len(results) if results else 0.0

    return {
        "accuracy":  round(accuracy,  3),
        "precision": round(precision, 3),
        "recall":    round(recall,    3),
        "f1":        round(f1,        3),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "total": len(results),
    }


def issue_type_score(result: dict) -> dict:
    """Check if detected issue types match expected error types."""
    expected_errors = {e["type"] for e in result.get("errors", [])}
    predicted_types = {i.get("type", "").upper() for i in result.get("predicted_issues", [])}

    # Normalise common aliases
    aliases = {"GROSS_WEIGHT_MISMATCH": "WEIGHT_MISMATCH", "WEIGHT": "WEIGHT_MISMATCH",
               "HS_MISMATCH": "HS_CODE_MISMATCH", "HS": "HS_CODE_MISMATCH"}
    predicted_types = {aliases.get(t, t) for t in predicted_types}

    correct_types = expected_errors & predicted_types
    return {
        "expected_types":   list(expected_errors),
        "predicted_types":  list(predicted_types),
        "correct_types":    list(correct_types),
        "type_match_score": len(correct_types) / len(expected_errors) if expected_errors else 1.0,
    }


# ── Main benchmark ─────────────────────────────────────────────────

def run_benchmark(
    labels_path: str = "data/ood_benchmark/labels.json",
    output_path: str = "outputs/benchmark_v2_results.json",
):
    # Load OOD labels
    if not os.path.exists(labels_path):
        print(f"❌ Labels not found: {labels_path}")
        print("   Run first: python3 training/generate_ood_benchmark.py")
        sys.exit(1)

    with open(labels_path) as f:
        labels = json.load(f)

    print(f"[Benchmark V2] {len(labels)} OOD samples loaded.")
    print("[Benchmark V2] Loading base Qwen2-VL-7B (this takes ~60s)...")

    from models.vlm_extractor import VLMExtractor
    extractor = VLMExtractor()

    results   = []
    parse_errors = 0
    start_all = time.time()

    for i, lbl in enumerate(labels):
        try:
            inv_img = pdf_to_pil(lbl["invoice_path"])
            pl_img  = pdf_to_pil(lbl["packing_list_path"])
        except Exception as e:
            print(f"  [SKIP] Sample {lbl['id']}: PDF load error — {e}")
            continue

        t0 = time.time()
        try:
            vlm_result = extractor.extract(inv_img, pl_img)
        except Exception as e:
            print(f"  [ERROR] Sample {lbl['id']}: {e}")
            vlm_result = {"status": "NEEDS_REVIEW", "issues": [], "parse_error": True}

        elapsed = time.time() - t0

        predicted_status = vlm_result.get("status", "NEEDS_REVIEW")
        expected_status  = lbl["expected_status"]
        correct = predicted_status == expected_status
        has_parse_error = vlm_result.get("parse_error", False)
        if has_parse_error: parse_errors += 1

        type_info = issue_type_score({
            "errors":           lbl["errors"],
            "predicted_issues": vlm_result.get("issues", []),
        })

        rec = {
            "id":               lbl["id"],
            "expected_status":  expected_status,
            "predicted_status": predicted_status,
            "correct":          correct,
            "parse_error":      has_parse_error,
            "elapsed_s":        round(elapsed, 2),
            "errors":           lbl["errors"],
            "predicted_issues": vlm_result.get("issues", []),
            "predicted_summary": vlm_result.get("summary", ""),
            "issue_type_score": type_info,
            "layout":           lbl.get("layout", -1),
            "product_category": lbl.get("product_category"),
            "exporter":         lbl.get("exporter"),
            "importer":         lbl.get("importer"),
        }
        results.append(rec)

        status_icon = "✅" if correct else "❌"
        parse_icon  = " [parse_err]" if has_parse_error else ""
        print(f"  {status_icon} [{i+1:02d}/{len(labels)}] "
              f"{expected_status:8s} → {predicted_status:12s} "
              f"({elapsed:.1f}s){parse_icon}")

    total_time = time.time() - start_all
    metrics = compute_metrics(results)

    # Save full results
    output = {
        "model":        "Qwen/Qwen2-VL-7B-Instruct (base, 4-bit)",
        "dataset":      labels_path,
        "total_samples": len(results),
        "parse_errors":  parse_errors,
        "total_time_s":  round(total_time, 1),
        "avg_time_s":    round(total_time / len(results), 2) if results else 0,
        "metrics":      metrics,
        "per_sample":   results,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # ── Print summary ──────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  BENCHMARK V2 — FINAL RESULTS")
    print(f"{'='*55}")
    print(f"  Model   : Qwen2-VL-7B-Instruct (base, 4-bit)")
    print(f"  Dataset : {len(results)} OOD pairs (unseen layout/entities)")
    print(f"  Time    : {total_time/60:.1f} min total | {output['avg_time_s']:.1f}s avg/sample")
    print(f"")
    print(f"  Accuracy  : {metrics['accuracy']*100:.1f}%")
    print(f"  Precision : {metrics['precision']*100:.1f}%  (REJECTED)")
    print(f"  Recall    : {metrics['recall']*100:.1f}%  (REJECTED)")
    print(f"  F1 Score  : {metrics['f1']*100:.1f}%")
    print(f"")
    print(f"  TP={metrics['tp']} FP={metrics['fp']} TN={metrics['tn']} FN={metrics['fn']}")
    print(f"  Parse errors: {parse_errors}/{len(results)}")
    print(f"")

    if metrics["accuracy"] >= 0.80:
        print(f"  ✅ PASS — Model generalises well (≥80% accuracy)")
        print(f"     Safe to integrate into /check_v3 endpoint.")
    elif metrics["accuracy"] >= 0.65:
        print(f"  ⚠️  MARGINAL — Recommend collecting more OOD data")
        print(f"     Consider hybrid: VLM + regex fallback.")
    else:
        print(f"  ❌ FAIL — Model not reliable enough for production")
        print(f"     Activate hybrid fallback to Phase 1+2 pipeline.")

    print(f"\n  Full results: {output_path}")
    print(f"{'='*55}\n")

    return metrics


if __name__ == "__main__":
    run_benchmark()
