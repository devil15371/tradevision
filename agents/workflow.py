"""
LangGraph Workflow — TradeVision HMAS
======================================
StateGraph wiring:

  START
    │
    ├──► [vlm_worker]    ─┐
    │                      ├──► [rag_worker] ──► [supervisor] ──► END
    └──► [regex_worker]  ─┘

VLM and Regex run in parallel (parallel_workers fan-out).
Their outputs are merged in the state before RAG runs.
Supervisor is always last — it synthesizes all worker outputs.
"""
from __future__ import annotations
import logging
import os
import tempfile
from typing import TypedDict, Any

from langgraph.graph import StateGraph, START, END

from agents.worker_vlm   import vlm_worker
from agents.worker_regex import regex_worker
from agents.worker_rag   import rag_worker
from agents.supervisor   import supervisor_node

logger = logging.getLogger(__name__)


# ── State schema ────────────────────────────────────────────────────────────

class HMASState(TypedDict, total=False):
    # Inputs
    inv_img:        Any   # PIL.Image
    pl_img:         Any   # PIL.Image
    inv_pdf_path:   str
    pl_pdf_path:    str

    # Worker outputs
    vlm_result:     dict
    regex_result:   dict
    rag_result:     list
    document_fields: dict

    # Supervisor output
    supervisor_result:  dict
    final_status:       str
    supervisor_available: bool

    # Convenience
    invoice_text:   str
    pl_text:        str


# ── Parallel fan-out helper ─────────────────────────────────────────────────

def parallel_workers(state: HMASState) -> HMASState:
    """
    Runs VLM and Regex workers in parallel using threads,
    then merges their outputs into state.

    LangGraph doesn't natively run Python threads, so we do it here
    with concurrent.futures and return merged state.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(vlm_worker, state):   "vlm",
            pool.submit(regex_worker, state): "regex",
        }
        for future in as_completed(futures):
            tag = futures[future]
            try:
                results[tag] = future.result()
            except Exception as e:
                logger.error(f"[parallel_workers] {tag} worker failed: {e}")
                results[tag] = {}

    merged = dict(state)
    merged.update(results.get("vlm",   {}))
    merged.update(results.get("regex", {}))
    return merged


# ── Graph definition ────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(HMASState)

    graph.add_node("parallel_workers", parallel_workers)
    graph.add_node("rag_worker",       rag_worker)
    graph.add_node("supervisor",       supervisor_node)

    graph.add_edge(START,              "parallel_workers")
    graph.add_edge("parallel_workers", "rag_worker")
    graph.add_edge("rag_worker",       "supervisor")
    graph.add_edge("supervisor",        END)

    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ── Public API ──────────────────────────────────────────────────────────────

def run_hmas_workflow(
    inv_img,     # PIL.Image — invoice
    pl_img,      # PIL.Image — packing list
    inv_pdf_path: str,
    pl_pdf_path:  str,
) -> dict:
    """
    Run the full HMAS pipeline.

    Args:
        inv_img:      PIL Image of invoice (first page, rendered at 2x)
        pl_img:       PIL Image of packing list
        inv_pdf_path: Absolute path to invoice PDF temp file
        pl_pdf_path:  Absolute path to packing list PDF temp file

    Returns:
        Full state dict after workflow completes, ready to be serialised
        as the /check_v4 API response.
    """
    logger.info("[Workflow] Starting HMAS run...")
    graph = _get_graph()

    initial_state: HMASState = {
        "inv_img":      inv_img,
        "pl_img":       pl_img,
        "inv_pdf_path": inv_pdf_path,
        "pl_pdf_path":  pl_pdf_path,
    }

    final_state = graph.invoke(initial_state)
    logger.info(f"[Workflow] Complete. final_status={final_state.get('final_status')}, "
                f"supervisor={'online' if final_state.get('supervisor_available') else 'fallback'}")
    return final_state
