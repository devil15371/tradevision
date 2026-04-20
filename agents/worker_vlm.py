"""
Worker: VLM Agent
=================
Wraps VLMExtractor into a LangGraph-compatible node.
Converts PDF PIL images → structured extraction dict.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)


def vlm_worker(state: dict) -> dict:
    """
    LangGraph node: Visual extraction via Qwen2-VL-7B.

    Reads:   state["inv_img"], state["pl_img"]
    Writes:  state["vlm_result"]
    """
    from models.vlm_extractor import VLMExtractor

    inv_img = state["inv_img"]
    pl_img  = state["pl_img"]

    logger.info("[Worker:VLM] Starting visual extraction...")
    extractor = VLMExtractor()
    result = extractor.extract(inv_img, pl_img)
    logger.info(f"[Worker:VLM] Done. status={result.get('status')}, issues={len(result.get('issues', []))}")

    return {"vlm_result": result}
