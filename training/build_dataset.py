"""
Build fine-tuning dataset from generated PDF pairs.
Converts each PDF page to a PNG image, encodes as base64,
and writes training samples in Qwen2-VL chat format to JSONL.

Run: python3 training/build_dataset.py
"""

import json
import fitz  # PyMuPDF
import os
import base64
from pathlib import Path


def pdf_page_to_base64(pdf_path: str, page_num: int = 0, scale: float = 2.0) -> str:
    """Convert a PDF page to a base64-encoded PNG string."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(scale, scale)  # 2x zoom for clarity
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode("utf-8")


def build_training_sample(label: dict) -> dict:
    """Build one training sample in Qwen2-VL multi-image chat format."""

    errors = label["errors"]
    expected = label["expected_status"]

    if expected == "PASSED":
        expected_output = json.dumps({
            "status": "PASSED",
            "issues": [],
            "summary": "Documents match. No compliance issues found."
        })
    else:
        issues = []
        for err in errors:
            if err["type"] == "WEIGHT_MISMATCH":
                issues.append({
                    "type": "WEIGHT_MISMATCH",
                    "severity": "HIGH",
                    "detail": (
                        f"Invoice weight {err['invoice_weight']}kg does not match "
                        f"packing list weight {err['packing_weight']}kg. "
                        f"Difference: {round(abs(err['packing_weight'] - err['invoice_weight']), 2)}kg"
                    )
                })
            elif err["type"] == "HS_CODE_MISMATCH":
                issues.append({
                    "type": "HS_CODE_MISMATCH",
                    "severity": "HIGH",
                    "detail": (
                        f"HS code {err['invoice_hs']} on invoice does not match "
                        f"{err['packing_hs']} on packing list"
                    )
                })

        expected_output = json.dumps({
            "status": "REJECTED",
            "issues": issues,
            "summary": f"Found {len(issues)} compliance issue(s) requiring correction before export."
        })

    invoice_b64 = pdf_page_to_base64(label["invoice_path"])
    packing_b64 = pdf_page_to_base64(label["packing_list_path"])

    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a customs compliance auditor for Indian exports. "
                            "Compare the commercial invoice and packing list provided. "
                            "Check for: (1) gross weight mismatches, (2) HS code mismatches, "
                            "(3) quantity discrepancies. "
                            "Return ONLY a JSON object with keys: status, issues, summary."
                        )
                    },
                    {
                        "type": "text",
                        "text": f"COMMERCIAL INVOICE (Document ID: {label['id']}):"
                    },
                    {
                        "type": "image",
                        "image": f"data:image/png;base64,{invoice_b64}"
                    },
                    {
                        "type": "text",
                        "text": "PACKING LIST:"
                    },
                    {
                        "type": "image",
                        "image": f"data:image/png;base64,{packing_b64}"
                    }
                ]
            },
            {
                "role": "assistant",
                "content": expected_output
            }
        ]
    }


def build_full_dataset(
    labels_path: str = "data/training/labels.json",
    output_path: str = "training/dataset.jsonl",
    max_samples: int | None = None
):
    os.makedirs("training", exist_ok=True)

    with open(labels_path) as f:
        labels = json.load(f)

    if max_samples:
        labels = labels[:max_samples]

    total = len(labels)
    print(f"Building dataset from {total} document pairs...")

    errors_count = 0
    written = 0

    with open(output_path, "w") as out:
        for i, label in enumerate(labels):
            try:
                sample = build_training_sample(label)
                out.write(json.dumps(sample) + "\n")
                written += 1
            except Exception as e:
                print(f"  [SKIP] Sample {label['id']}: {e}")
                errors_count += 1
                continue

            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{total}  ({errors_count} errors)")

    print(f"\nDataset complete!")
    print(f"  Written : {written} samples")
    print(f"  Skipped : {errors_count} samples")
    print(f"  Output  : {output_path}")

    # Print label distribution
    passed = sum(1 for l in labels[:written] if l["expected_status"] == "PASSED")
    rejected = written - passed
    print(f"  PASSED  : {passed} | REJECTED: {rejected}")


if __name__ == "__main__":
    import sys
    max_s = int(sys.argv[1]) if len(sys.argv) > 1 else None
    build_full_dataset(max_samples=max_s)
