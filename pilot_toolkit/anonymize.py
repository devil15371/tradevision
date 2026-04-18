"""
TradeVision Pilot Toolkit — Tier 1 Local PDF Anonymizer
=========================================================
Lightweight standalone script for Custom House Agents (CHAs).

REQUIREMENTS (all CPU-only, ~100MB download):
    pip install PyMuPDF pytesseract Pillow
    sudo apt install tesseract-ocr   # Linux
    brew install tesseract           # macOS

HOW TO RUN:
    1. Place your PDF files in a folder called  input_pdfs/
    2. Run:  python anonymize.py
    3. Collect your REDACTED_*.pdf files from  output_redacted/

The script:
  - Uses Tesseract OCR (CPU-only) to locate sensitive text on each page.
  - Draws solid black boxes over: buyer names, prices, amounts,
    invoice values, email addresses, and currency figures.
  - Extends each box 500px to the right so the data NEXT TO the
    label is also covered.
  - Flattens every page to a flat image PDF (no underlying text layer
    that could be copy-pasted).

The redaction core (redactor.py) is shared with the TradeVision API.
"""

import os
import sys
import argparse

try:
    import fitz
except ImportError:
    os.system("pip install PyMuPDF -q")
    import fitz

from PIL import Image
import io

# ── Import shared redaction core ──────────────────────────────────────
# If run from pilot_toolkit/ directory, add project root to path.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from models.redactor import redact_image   # shared core, CPU mode


def anonymize_pdf(input_path: str, output_path: str, dpi: int = 150) -> int:
    """
    Convert each PDF page to image → redact → save as image-only PDF.

    Returns number of pages processed.
    """
    doc = fitz.open(input_path)
    output_doc = fitz.open()
    total_pages = len(doc)

    for page_num, page in enumerate(doc):
        # Render page to image
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Redact using CPU/tesseract backend
        redacted = redact_image(img, use_gpu=False)

        # Convert redacted PIL image back to PDF page
        img_bytes = io.BytesIO()
        redacted.save(img_bytes, format="PDF")
        img_bytes.seek(0)
        page_doc = fitz.open("pdf", img_bytes.read())
        output_doc.insert_pdf(page_doc)

    output_doc.save(output_path, garbage=4, deflate=True)
    output_doc.close()
    doc.close()
    return total_pages


def main():
    parser = argparse.ArgumentParser(
        description="TradeVision Local PDF Anonymizer — redacts sensitive trade data before sharing."
    )
    parser.add_argument("--input", "-i", default="input_pdfs",
                        help="Input directory containing PDF files (default: input_pdfs/)")
    parser.add_argument("--output", "-o", default="output_redacted",
                        help="Output directory for anonymized PDFs (default: output_redacted/)")
    parser.add_argument("--dpi", type=int, default=150,
                        help="Rendering DPI for image quality (default: 150)")
    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"❌ Input folder not found: '{args.input}'")
        print(f"   Create the folder and place your PDFs inside it, then run again.")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)
    pdfs = [f for f in os.listdir(args.input) if f.lower().endswith(".pdf")]

    if not pdfs:
        print(f"❌ No PDF files found in '{args.input}'")
        sys.exit(1)

    print(f"\n🔒 TradeVision Local PDF Anonymizer")
    print(f"   Input : {args.input}/ ({len(pdfs)} files)")
    print(f"   Output: {args.output}/")
    print(f"   DPI   : {args.dpi}\n")

    for fname in sorted(pdfs):
        in_path  = os.path.join(args.input, fname)
        out_name = f"REDACTED_{fname}"
        out_path = os.path.join(args.output, out_name)
        print(f"  Processing: {fname}")
        try:
            pages = anonymize_pdf(in_path, out_path, dpi=args.dpi)
            print(f"  ✅ Done ({pages} pages) → {out_name}\n")
        except Exception as e:
            print(f"  ❌ Failed: {e}\n")

    print("All files processed. Share the contents of the output folder.")


if __name__ == "__main__":
    main()
