"""
Worker: RAG Compliance Agent
==============================
Wraps the RAGChecker into a LangGraph node.
Runs after VLM + Regex workers have populated state.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def rag_worker(state: dict) -> dict:
    """
    LangGraph node: RAG regulatory check.

    Reads:   state["invoice_text"], state["vlm_result"], state["regex_result"]
    Writes:  state["rag_result"]   (list of regulatory flag dicts)
    """
    from models.llm_extractor import LLMExtractor
    from models.rag_checker import RAGChecker

    invoice_text = state.get("invoice_text", "")
    vlm_issues   = state.get("vlm_result", {}).get("issues", [])
    regex_issues = state.get("regex_result", {}).get("issues", [])

    # Merge issue types from both workers
    issue_types = list(set(
        [i.get("type", "").upper() for i in vlm_issues] +
        [i.get("type", "").upper() for i in regex_issues]
    ))

    logger.info("[Worker:RAG] Extracting LLM fields...")
    extractor = LLMExtractor()
    fields = extractor.extract(invoice_text)

    logger.info(f"[Worker:RAG] Querying regulations for {fields.get('product_category','?')} / {issue_types}...")
    checker = RAGChecker()
    flags = checker.check(
        doc_text=invoice_text,
        hs_codes=fields.get("hs_codes", []),
        product_category=fields.get("product_category", "general"),
        triggered_issues=issue_types,
    )
    logger.info(f"[Worker:RAG] Done. flags={len(flags)} ({sum(1 for f in flags if f['severity']=='CRITICAL')} critical)")

    return {
        "rag_result":      flags,
        "document_fields": fields,
    }
