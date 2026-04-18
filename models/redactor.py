"""
redactor.py — Shared Core Redaction Engine
============================================
Single source of truth for redaction logic.

Used by:
  - pilot_toolkit/anonymize.py  (Tier 1: lightweight, CPU-only tesseract)
  - main.py /check_v3           (Tier 2: fast GPU easyocr on H100)

The public API is a single function:
    redact_image(img: PIL.Image, use_gpu: bool = False) -> PIL.Image

It finds bounding boxes for all sensitive text on the image and draws
solid black rectangles over them (plus a configurable right-side buffer
to cover the values/names that appear *next to* the keyword label).
"""

from __future__ import annotations
import re
from typing import Sequence

from PIL import Image, ImageDraw

# ── Kill List ──────────────────────────────────────────────────────────────
# Redact every line whose text STARTS WITH or CONTAINS any of these tokens.
# The buffer logic (see LABEL_RIGHT_BUFFER_PX) extends the black box rightward
# to cover the actual data value printed next to the label.

KILL_KEYWORDS: list[str] = [
    # Buyer / Party identifiers
    "buyer", "consignee", "notify party", "shipper",
    "exporter", "importer", "sold to", "bill to",
    # Financial fields
    "unit price", "price per", "amount", "total", "sub-total",
    "invoice value", "fob value", "cif value",
    "discount", "tax", "gst", "freight charges",
    # Currency symbols caught by regex pattern below
]

KILL_REGEX: list[str] = [
    r"\$\s*[\d,]+(?:\.\d{2})?",            # $1,234.56
    r"(?:USD|INR|EUR|GBP)\s*[\d,]+(?:\.\d{2})?",  # USD 1234.00
    r"(?:Rs\.?|₹)\s*[\d,]+(?:\.\d{2})?",  # Rs. 1234  /  ₹1234
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b",  # emails
]

# Extra pixels to extend the black box to the right of a matched keyword
# to cover the value/name printed next to it on the same line.
LABEL_RIGHT_BUFFER_PX: int = 500


# ── Tesseract backend (CPU / lightweight) ──────────────────────────────────

def _find_boxes_tesseract(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """
    Returns list of (x0, y0, x1, y1) boxes for sensitive text.
    Requires: pytesseract + tesseract-ocr system package.
    """
    import pytesseract

    w, h = img.size
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    boxes: list[tuple[int, int, int, int]] = []
    n = len(data["text"])

    for i in range(n):
        word = (data["text"][i] or "").strip().lower()
        if not word:
            continue

        x = data["left"][i]
        y = data["top"][i]
        bw = data["width"][i]
        bh = data["height"][i]

        hit = False

        # Keyword match
        for kw in KILL_KEYWORDS:
            if kw in word:
                hit = True
                break

        # Regex match
        if not hit:
            for pat in KILL_REGEX:
                if re.search(pat, data["text"][i], re.IGNORECASE):
                    hit = True
                    break

        if hit:
            # Extend box rightward — covers the value/name next to the label
            x0 = max(0, x - 4)
            y0 = max(0, y - 4)
            x1 = min(w, x + bw + LABEL_RIGHT_BUFFER_PX)
            y1 = min(h, y + bh + 4)
            boxes.append((x0, y0, x1, y1))

    return boxes


# ── EasyOCR backend (GPU / high-accuracy) ─────────────────────────────────

_easyocr_reader = None  # lazy singleton


def _get_easyocr_reader(gpu: bool = True):
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)
    return _easyocr_reader


def _find_boxes_easyocr(img: Image.Image, gpu: bool = True) -> list[tuple[int, int, int, int]]:
    """
    Returns list of (x0, y0, x1, y1) boxes.
    EasyOCR returns polygon coordinates; we convert to axis-aligned bbox.
    """
    import numpy as np

    reader = _get_easyocr_reader(gpu)
    img_np = np.array(img)
    w, h = img.size

    # detail=1 returns (bbox, text, confidence)
    results = reader.readtext(img_np, detail=1)
    boxes: list[tuple[int, int, int, int]] = []

    for bbox_poly, text, _conf in results:
        word = (text or "").strip().lower()
        if not word:
            continue

        hit = False
        for kw in KILL_KEYWORDS:
            if kw in word:
                hit = True
                break
        if not hit:
            for pat in KILL_REGEX:
                if re.search(pat, text, re.IGNORECASE):
                    hit = True
                    break

        if hit:
            xs = [p[0] for p in bbox_poly]
            ys = [p[1] for p in bbox_poly]
            x0 = max(0, int(min(xs)) - 4)
            y0 = max(0, int(min(ys)) - 4)
            # Extend rightward to cover value next to label
            x1 = min(w, int(max(xs)) + LABEL_RIGHT_BUFFER_PX)
            y1 = min(h, int(max(ys)) + 4)
            boxes.append((x0, y0, x1, y1))

    return boxes


# ── Public API ─────────────────────────────────────────────────────────────

def redact_image(
    img: Image.Image,
    use_gpu: bool = False,
    fill_color: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """
    Redact sensitive regions in a PIL Image.

    Args:
        img:        Input PIL Image (RGB).
        use_gpu:    If True, uses EasyOCR on GPU (fast, accurate — H100).
                    If False, uses pytesseract (CPU-only, lightweight).
        fill_color: RGB colour for the blackout boxes. Default = black.

    Returns:
        A new PIL Image with sensitive areas covered by solid boxes.
    """
    img = img.convert("RGB")

    if use_gpu:
        boxes = _find_boxes_easyocr(img, gpu=True)
    else:
        boxes = _find_boxes_tesseract(img)

    if not boxes:
        return img  # nothing to redact

    out = img.copy()
    draw = ImageDraw.Draw(out)
    for (x0, y0, x1, y1) in boxes:
        draw.rectangle([x0, y0, x1, y1], fill=fill_color)

    return out
