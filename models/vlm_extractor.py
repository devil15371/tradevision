"""
VLM Extractor — Phase 3
Uses base Qwen2-VL-7B-Instruct in 4-bit quantization for zero-shot
visual compliance checking of trade document image pairs.

Uses unsloth FastVisionModel for optimised inference on the cached
4-bit weights. Lazy-loaded singleton: model loads once at API startup.

Usage:
    extractor = VLMExtractor()
    result = extractor.extract(invoice_pil_image, packing_list_pil_image)
    # result: {"status": "PASSED"|"REJECTED"|"NEEDS_REVIEW",
    #          "issues": [...], "summary": "..."}
"""

import unsloth  # must be first — patches transformers before anything else loads
import json
import re
import os
import sys
import logging

logger = logging.getLogger(__name__)

BASE_MODEL_ID = "unsloth/qwen2-vl-7b-instruct-unsloth-bnb-4bit"

# System prompt — instructs the model to return strict JSON
SYSTEM_PROMPT = (
    "You are a customs compliance auditor specialising in Indian export documents. "
    "Analyse the commercial invoice and packing list images provided. "
    "Identify ONLY the following discrepancy types:\n"
    "  1. WEIGHT_MISMATCH — gross weight on invoice differs from packing list\n"
    "  2. HS_CODE_MISMATCH — HS/tariff code on invoice differs from packing list\n\n"
    "Return ONLY a valid JSON object with EXACTLY these keys:\n"
    '  "status": "PASSED" or "REJECTED"\n'
    '  "issues": list of objects, each with: "type", "severity" ("HIGH"), "detail"\n'
    '  "summary": one-sentence human-readable verdict\n\n'
    "If documents match, return status=PASSED with empty issues list. "
    "Do NOT include any text outside the JSON object."
)

USER_PROMPT = (
    "Compare the COMMERCIAL INVOICE and PACKING LIST shown below. "
    "Return the JSON compliance verdict."
)


class VLMExtractor:
    """
    Inference-only wrapper around base Qwen2-VL-7B-Instruct.
    Thread-safe: single model instance, stateless inference.
    """

    _instance = None  # singleton

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._model = None
        self._processor = None
        self._initialized = True

    def _load(self):
        """Lazy-load model on first inference call."""
        if self._model is not None:
            return

        logger.info("[VLMExtractor] Loading Qwen2-VL-7B-Instruct (unsloth 4-bit cached)...")

        from unsloth import FastVisionModel
        from transformers import AutoProcessor

        self._model, _tokenizer = FastVisionModel.from_pretrained(
            BASE_MODEL_ID,
            load_in_4bit=True,
        )
        FastVisionModel.for_inference(self._model)

        self._processor = AutoProcessor.from_pretrained(
            BASE_MODEL_ID,
            trust_remote_code=True,
        )

        logger.info("[VLMExtractor] Model loaded and ready.")

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    def extract(self, invoice_img, packing_list_img, max_new_tokens: int = 512) -> dict:
        """
        Run VLM inference on a (invoice, packing_list) PIL image pair.

        Args:
            invoice_img:       PIL.Image — rendered invoice page
            packing_list_img:  PIL.Image — rendered packing list page
            max_new_tokens:    Token budget for the response

        Returns:
            dict with keys: status, issues, summary
            On failure: {"status": "NEEDS_REVIEW", "issues": [], "parse_error": True, "raw": ...}
        """
        self._load()

        import torch

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {"type": "text", "text": "\n\nCOMMERCIAL INVOICE:"},
                    {"type": "image", "image": invoice_img},
                    {"type": "text", "text": "\nPACKING LIST:"},
                    {"type": "image", "image": packing_list_img},
                    {"type": "text", "text": f"\n\n{USER_PROMPT}"},
                ],
            }
        ]

        text_input = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Process with images
        inputs = self._processor(
            text=[text_input],
            images=[invoice_img, packing_list_img],
            padding=True,
            return_tensors="pt",
        )
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=1.0,      # ignored when do_sample=False
                repetition_penalty=1.05,
            )

        # Decode only generated tokens (strip the input prefix)
        new_tokens = output_ids[:, inputs["input_ids"].shape[1]:]
        raw = self._processor.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()

        return self._parse(raw)

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    @staticmethod
    def _parse(raw: str) -> dict:
        """Extract and parse JSON from raw model output."""
        # Find the outermost {...} block
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                parsed = json.loads(match.group())
                # Normalise keys
                status = str(parsed.get("status", "NEEDS_REVIEW")).upper()
                if status not in ("PASSED", "REJECTED"):
                    status = "NEEDS_REVIEW"
                issues = parsed.get("issues", [])
                summary = parsed.get("summary", "")
                return {"status": status, "issues": issues, "summary": summary}
            except json.JSONDecodeError:
                pass

        # Fallback: try to infer status from keywords
        lower = raw.lower()
        if "rejected" in lower or "mismatch" in lower:
            status = "REJECTED"
        elif "passed" in lower or "no issue" in lower or "match" in lower:
            status = "PASSED"
        else:
            status = "NEEDS_REVIEW"

        return {
            "status": status,
            "issues": [],
            "summary": "Could not parse structured output.",
            "parse_error": True,
            "raw_output": raw[:500],
        }


def _pdf_to_pil(pdf_path: str):
    """Convert PDF page 0 to PIL Image."""
    import fitz
    from PIL import Image
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


# ─────────────────────────────────────────────
# Standalone smoke test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json as _json

    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

    extractor = VLMExtractor()

    for label, inv, pl, expected in [
        ("Matching docs",   "invoice_1_correct.pdf",  "packing_list_1_correct.pdf", "PASSED"),
        ("Mismatched docs", "invoice_2_errors.pdf",   "packing_list_2_errors.pdf",  "REJECTED"),
    ]:
        inv_img = _pdf_to_pil(os.path.join(DATA_DIR, inv))
        pl_img  = _pdf_to_pil(os.path.join(DATA_DIR, pl))

        print(f"\n--- {label} (expected: {expected}) ---")
        result = extractor.extract(inv_img, pl_img)
        ok = result.get("status") == expected
        print(f"{'✅ PASS' if ok else '❌ FAIL'} — status: {result['status']}")
        print(_json.dumps(result, indent=2))
