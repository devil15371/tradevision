from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import tempfile
import os
import sys
import base64
import io
import logging

logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extraction.extract import extract_document
from extraction.compare import compare_invoice_packing_list
from models.llm_extractor import LLMExtractor
from models.rag_checker import RAGChecker
from models.vlm_extractor import VLMExtractor
from models.redactor import redact_image
from agents.workflow import run_hmas_workflow

# ── Singletons — loaded once at startup ──────────────────────────
_extractor: LLMExtractor = None
_rag_checker: RAGChecker = None
_vlm_extractor: VLMExtractor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _extractor, _rag_checker, _vlm_extractor
    print("[TradeVision] Loading Phase 2 models...")
    _extractor = LLMExtractor()
    _rag_checker = RAGChecker()
    print("[TradeVision] Phase 2 ready.")
    print("[TradeVision] Pre-loading Phase 3 VLM (Qwen2-VL-7B-Instruct)...")
    _vlm_extractor = VLMExtractor()
    _vlm_extractor._load()   # eagerly warm the model at startup
    print("[TradeVision] All models ready.")
    yield


app = FastAPI(
    title="TradeVision API",
    description="AI-powered trade document compliance checker for Indian exporters",
    version="0.4.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "message": "TradeVision API is running",
        "version": "0.4.0",
        "endpoints": {
            "/compare":    "Phase 1 — regex-based document comparison",
            "/check_full": "Phase 2 — regex + LLM field extraction + RAG compliance",
            "/check_v3":   "Phase 3 — VLM visual extraction + RAG compliance",
            "/check_v4":   "Phase 4 — HMAS: Supervisor (Qwen3-30B-A3B) + VLM + Regex + RAG agents",
        }
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/extract")
async def extract_single_document(file: UploadFile = File(...)):
    """Extract text from a single trade document"""

    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = extract_document(tmp_path)
        return {
            "filename": file.filename,
            "pages": result["page_count"],
            "text_preview": result["text"][:1000],
            "full_text_length": len(result["text"])
        }
    finally:
        os.unlink(tmp_path)


@app.post("/compare")
async def compare_documents(
    invoice: UploadFile = File(...),
    packing_list: UploadFile = File(...)
):
    """Phase 1: Compare invoice against packing list — regex only."""

    for f in [invoice, packing_list]:
        if not f.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"{f.filename} must be a PDF")

    tmp_invoice = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_packing = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    try:
        tmp_invoice.write(await invoice.read())
        tmp_invoice.close()
        tmp_packing.write(await packing_list.read())
        tmp_packing.close()

        invoice_data = extract_document(tmp_invoice.name)
        packing_data = extract_document(tmp_packing.name)

        comparison_result = compare_invoice_packing_list(
            invoice_data["text"],
            packing_data["text"]
        )

        return {
            "invoice_file": invoice.filename,
            "packing_list_file": packing_list.filename,
            "result": comparison_result
        }

    finally:
        os.unlink(tmp_invoice.name)
        os.unlink(tmp_packing.name)


@app.post("/check_full")
async def check_full(
    invoice: UploadFile = File(...),
    packing_list: UploadFile = File(...)
):
    """
    Phase 2: Full compliance check.
    Combines Phase 1 regex comparison + LLM field extraction + RAG regulatory check.
    Returns a comprehensive JSON with issues, document fields, and regulatory flags.
    """

    for f in [invoice, packing_list]:
        if not f.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"{f.filename} must be a PDF")

    tmp_invoice = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_packing = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    try:
        tmp_invoice.write(await invoice.read())
        tmp_invoice.close()
        tmp_packing.write(await packing_list.read())
        tmp_packing.close()

        # --- Extract PDF text ---
        invoice_data = extract_document(tmp_invoice.name)
        packing_data = extract_document(tmp_packing.name)

        # --- Phase 1: Regex comparison ---
        comparison = compare_invoice_packing_list(
            invoice_data["text"],
            packing_data["text"]
        )

        # --- Phase 2a: Field extraction ---
        fields = _extractor.extract(invoice_data["text"])

        # --- Phase 2b: RAG regulatory check ---
        triggered_issue_types = [i["type"] for i in comparison["issues"]]
        regulatory_flags = _rag_checker.check(
            doc_text=invoice_data["text"],
            hs_codes=fields["hs_codes"],
            product_category=fields["product_category"],
            triggered_issues=triggered_issue_types,
        )

        # --- Determine final status ---
        has_critical = any(f["severity"] == "CRITICAL" for f in regulatory_flags
                           if f["match_type"] in ("HS_CODE_REGULATORY_FLAG", "MISMATCH_PENALTY_RISK"))
        if comparison["status"] == "REJECTED" or has_critical:
            final_status = "REJECTED"
        elif comparison["status"] == "NEEDS_REVIEW" or regulatory_flags:
            final_status = "NEEDS_REVIEW"
        else:
            final_status = "PASSED"

        return {
            "status": final_status,
            "invoice_file": invoice.filename,
            "packing_list_file": packing_list.filename,
            "document_fields": fields,
            "issues": comparison["issues"],
            "warnings": comparison["warnings"],
            "regulatory_flags": regulatory_flags,
            "summary": {
                "phase1_status": comparison["status"],
                "issues_count": len(comparison["issues"]),
                "regulatory_flags_count": len(regulatory_flags),
                "critical_flags": sum(1 for f in regulatory_flags if f["severity"] == "CRITICAL"),
            }
        }

    finally:
        os.unlink(tmp_invoice.name)
        os.unlink(tmp_packing.name)


@app.post("/check_v3")
async def check_v3(
    invoice: UploadFile = File(...),
    packing_list: UploadFile = File(...),
    redact_sensitive: bool = Form(False),
):
    """
    Phase 3: VLM-powered compliance check.
    Uses base Qwen2-VL-7B-Instruct (4-bit) to visually analyse document image
    pairs, then routes extracted issues through the Phase 2 RAG compliance engine.

    Pipeline:
      1. PDF → PIL image (both documents)
      2. VLM extracts status + issues (weight / HS code mismatches) visually
      3. Phase 1 regex comparison run in parallel for cross-validation
      4. Extracted fields piped into RAG regulatory checker
      5. Final status = strictest of VLM + Phase 1 decisions
    """
    import fitz
    from PIL import Image as PILImage

    for f in [invoice, packing_list]:
        if not f.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{f.filename} must be a PDF")

    tmp_invoice = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_packing = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    try:
        tmp_invoice.write(await invoice.read())
        tmp_invoice.close()
        tmp_packing.write(await packing_list.read())
        tmp_packing.close()

        # ── PDF → PIL (for VLM) ───────────────────────────────────
        def _pdf_to_pil(path: str):
            doc = fitz.open(path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            return img

        inv_img = _pdf_to_pil(tmp_invoice.name)
        pl_img  = _pdf_to_pil(tmp_packing.name)

        # ── Optional: Redact sensitive fields before VLM sees them ──
        redacted_images_b64: dict = {}
        if redact_sensitive:
            logger.info("[Redactor] Running GPU redaction on invoice + packing list...")
            inv_img = redact_image(inv_img, use_gpu=True)
            pl_img  = redact_image(pl_img,  use_gpu=True)

            def _pil_to_b64(img):
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode()

            redacted_images_b64 = {
                "invoice":      _pil_to_b64(inv_img),
                "packing_list": _pil_to_b64(pl_img),
            }
            logger.info("[Redactor] Redaction complete.")

        # ── Phase 3: VLM visual extraction ───────────────────────
        vlm_result = _vlm_extractor.extract(inv_img, pl_img)
        vlm_status = vlm_result.get("status", "NEEDS_REVIEW")
        vlm_issues = vlm_result.get("issues", [])

        # ── Phase 1: Regex comparison (cross-validation) ─────────
        invoice_data = extract_document(tmp_invoice.name)
        packing_data = extract_document(tmp_packing.name)
        comparison   = compare_invoice_packing_list(
            invoice_data["text"], packing_data["text"]
        )

        # ── Phase 2a: LLM field extraction for RAG ───────────────
        fields = _extractor.extract(invoice_data["text"])

        # ── Phase 2b: RAG regulatory check ───────────────────────
        # Combine issue types from both VLM and regex for comprehensive RAG query
        vlm_issue_types  = [i.get("type", "").upper() for i in vlm_issues]
        regex_issue_types = [i["type"] for i in comparison["issues"]]
        all_issue_types  = list(set(vlm_issue_types + regex_issue_types))

        regulatory_flags = _rag_checker.check(
            doc_text=invoice_data["text"],
            hs_codes=fields["hs_codes"],
            product_category=fields["product_category"],
            triggered_issues=all_issue_types,
        )

        # ── Final status — strictest of VLM + Phase 1 ────────────
        has_critical = any(
            f["severity"] == "CRITICAL"
            for f in regulatory_flags
            if f["match_type"] in ("HS_CODE_REGULATORY_FLAG", "MISMATCH_PENALTY_RISK")
        )

        is_rejected = (
            vlm_status == "REJECTED"
            or comparison["status"] == "REJECTED"
            or has_critical
        )
        is_review = (
            vlm_status == "NEEDS_REVIEW"
            or comparison["status"] == "NEEDS_REVIEW"
            or bool(regulatory_flags)
        )

        if is_rejected:
            final_status = "REJECTED"
        elif is_review:
            final_status = "NEEDS_REVIEW"
        else:
            final_status = "PASSED"

        return {
            "status":             final_status,
            "invoice_file":       invoice.filename,
            "packing_list_file":  packing_list.filename,
            "redaction_applied":  redact_sensitive,
            "redacted_images":    redacted_images_b64,
            "vlm_result": {
                "status":  vlm_status,
                "issues":  vlm_issues,
                "summary": vlm_result.get("summary", ""),
                "parse_error": vlm_result.get("parse_error", False),
            },
            "phase1_comparison": {
                "status": comparison["status"],
                "issues": comparison["issues"],
                "warnings": comparison["warnings"],
            },
            "document_fields":    fields,
            "regulatory_flags":   regulatory_flags,
            "summary": {
                "vlm_status":            vlm_status,
                "phase1_status":         comparison["status"],
                "final_status":          final_status,
                "vlm_issues_count":      len(vlm_issues),
                "phase1_issues_count":   len(comparison["issues"]),
                "regulatory_flags_count": len(regulatory_flags),
                "critical_flags":        sum(1 for f in regulatory_flags if f["severity"] == "CRITICAL"),
            }
        }

    finally:
        os.unlink(tmp_invoice.name)
        os.unlink(tmp_packing.name)

# ── Phase 4: HMAS endpoint ────────────────────────────────────────

@app.post("/check_v4")
async def check_v4(
    invoice: UploadFile = File(...),
    packing_list: UploadFile = File(...),
    redact_sensitive: bool = Form(False),
):
    """
    Phase 4: Hierarchical Multi-Agent System (HMAS).

    Pipeline (LangGraph):
      ┌─ VLM Worker    (Qwen2-VL-7B, parallel) ─┐
      │                                            ├─► RAG Worker ─► Supervisor (Qwen3-30B-A3B) ─► Verdict
      └─ Regex Worker  (deterministic, parallel)  ─┘

    Returns full worker traces + Supervisor audit report.
    """
    import fitz
    from PIL import Image as PILImage

    for f in [invoice, packing_list]:
        if not f.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{f.filename} must be a PDF")

    tmp_invoice = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_packing = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    try:
        tmp_invoice.write(await invoice.read())
        tmp_invoice.close()
        tmp_packing.write(await packing_list.read())
        tmp_packing.close()

        # ── PDF → PIL ───────────────────────────────────────────
        def _pdf_to_pil(path: str) -> PILImage.Image:
            doc = fitz.open(path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            return img

        inv_img = _pdf_to_pil(tmp_invoice.name)
        pl_img  = _pdf_to_pil(tmp_packing.name)

        # ── Optional redaction before agents see documents ───────
        if redact_sensitive:
            inv_img = redact_image(inv_img, use_gpu=True)
            pl_img  = redact_image(pl_img,  use_gpu=True)

        # ── Run HMAS workflow ────────────────────────────────────
        result = run_hmas_workflow(
            inv_img=inv_img,
            pl_img=pl_img,
            inv_pdf_path=tmp_invoice.name,
            pl_pdf_path=tmp_packing.name,
        )

        # ── Serialise (PIL images are not JSON-serialisable) ─────
        sup   = result.get("supervisor_result", {})
        vlm   = result.get("vlm_result", {})
        regex = result.get("regex_result", {})
        rag   = result.get("rag_result", [])
        fields = result.get("document_fields", {})
        final_status = result.get("final_status", "NEEDS_REVIEW")

        return {
            "status":              final_status,
            "invoice_file":        invoice.filename,
            "packing_list_file":   packing_list.filename,
            "redaction_applied":   redact_sensitive,
            "supervisor_available": result.get("supervisor_available", False),

            # Supervisor synthesis
            "supervisor": {
                "final_status":          sup.get("final_status", final_status),
                "confidence":            sup.get("confidence", "LOW"),
                "audit_report":          sup.get("audit_report", ""),
                "risk_summary":          sup.get("risk_summary"),
                "key_issues":            sup.get("key_issues", []),
                "supervisor_reasoning":  sup.get("supervisor_reasoning", ""),
            },

            # Worker traces
            "agent_trace": {
                "vlm_worker": {
                    "status":      vlm.get("status"),
                    "issues":      vlm.get("issues", []),
                    "summary":     vlm.get("summary", ""),
                    "parse_error": vlm.get("parse_error", False),
                },
                "regex_worker": {
                    "status":   regex.get("status"),
                    "issues":   regex.get("issues", []),
                    "warnings": regex.get("warnings", []),
                },
                "rag_worker": {
                    "flags_count":  len(rag),
                    "critical":     sum(1 for f in rag if f.get("severity") == "CRITICAL"),
                    "flags":        rag,
                },
            },

            "document_fields":  fields,
            "regulatory_flags": rag,

            "summary": {
                "final_status":           final_status,
                "vlm_status":             vlm.get("status"),
                "regex_status":           regex.get("status"),
                "total_issues":           len(vlm.get("issues", [])) + len(regex.get("issues", [])),
                "regulatory_flags_count": len(rag),
                "critical_flags":         sum(1 for f in rag if f.get("severity") == "CRITICAL"),
                "supervisor_confidence":  sup.get("confidence", "LOW"),
            },
        }

    finally:
        os.unlink(tmp_invoice.name)
        os.unlink(tmp_packing.name)


# ── Data file download ────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


@app.get("/files")
def list_files():
    """List all sample PDFs available for download."""
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".pdf"))
    return {"files": files, "tip": "GET /download/{filename} to download"}


@app.get("/download/{filename}")
def download_file(filename: str):
    """Download a sample PDF directly from the server."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"{filename} not found. GET /files to see available files.")
    return FileResponse(path=file_path, filename=filename, media_type="application/pdf")
