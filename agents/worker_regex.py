"""
Worker: Regex Comparison Agent
================================
Wraps the deterministic Phase 1 engine into a LangGraph node.
Extracts text from PDF paths and runs weight/HS code cross-check.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def regex_worker(state: dict) -> dict:
    """
    LangGraph node: Deterministic regex comparison.

    Reads:   state["inv_pdf_path"], state["pl_pdf_path"]
    Writes:  state["regex_result"], state["invoice_text"], state["pl_text"]
    """
    from extraction.extract import extract_document
    from extraction.compare import compare_invoice_packing_list

    logger.info("[Worker:Regex] Extracting text and running comparison...")
    inv_data = extract_document(state["inv_pdf_path"])
    pl_data  = extract_document(state["pl_pdf_path"])
    comparison = compare_invoice_packing_list(inv_data["text"], pl_data["text"])
    logger.info(f"[Worker:Regex] Done. status={comparison['status']}, issues={len(comparison['issues'])}")

    return {
        "regex_result":  comparison,
        "invoice_text":  inv_data["text"],
        "pl_text":       pl_data["text"],
    }
