"""
Supervisor Agent — Qwen3-30B-A3B via vLLM
==========================================
The "Judge" of the multi-agent system.
Receives structured outputs from all three workers and:
  1. Makes the final Pass/Fail/Needs-Review judgment
  2. Writes a plain-English Audit Report
  3. If REJECTED, writes a Risk Summary citing the specific penalty clause

Connects to the local vLLM OpenAI-compatible server on port 8001.
Falls back gracefully if the Supervisor server is unavailable.
"""
from __future__ import annotations
import json
import logging
import os

logger = logging.getLogger(__name__)

SUPERVISOR_URL = os.getenv("SUPERVISOR_URL", "http://localhost:8001/v1")
SUPERVISOR_MODEL = os.getenv("SUPERVISOR_MODEL", "Qwen/Qwen3-30B-A3B")

# ── System prompt ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are TradeVision's Senior Customs Auditor AI — an expert in Indian export compliance law, DGFT regulations, and Customs Act 1962 penalty clauses.

You receive structured JSON reports from three specialist worker agents:
1. VLM Worker — visual extraction from document images
2. Regex Worker — deterministic weight and HS code comparison
3. RAG Worker — relevant regulatory flags from the Indian Customs knowledge base

Your job is to:
1. Synthesize all three reports into a single, authoritative compliance verdict.
2. Write a professional "Audit Report" in 2-4 sentences explaining the verdict in plain English.
3. If the verdict is REJECTED, write a "Risk Summary" citing the *specific* penalty clause, the *exact* discrepancy that triggered it, and the *potential financial or legal consequence*.
4. Be precise. Never guess. Only cite laws that appear in the RAG Worker output.
5. If there are no issues, confirm clearance concisely.

Respond ONLY with valid JSON in this exact schema:
{
  "final_status": "PASSED" | "REJECTED" | "NEEDS_REVIEW",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "audit_report": "<2-4 sentence professional summary>",
  "risk_summary": "<specific penalty, clause, and consequence — null if PASSED>",
  "key_issues": ["<concise issue 1>", "<concise issue 2>"],
  "supervisor_reasoning": "<1-2 sentences on how you weighed conflicting signals>"
}"""


def _build_user_message(state: dict) -> str:
    """Format worker outputs into a structured context block for the Supervisor."""
    vlm = state.get("vlm_result", {})
    regex = state.get("regex_result", {})
    rag = state.get("rag_result", [])
    fields = state.get("document_fields", {})

    # Summarize regulatory flags
    crit_flags = [f for f in rag if f.get("severity") == "CRITICAL"]
    high_flags  = [f for f in rag if f.get("severity") == "HIGH"]

    context = {
        "vlm_worker_output": {
            "status": vlm.get("status", "UNKNOWN"),
            "issues_found": vlm.get("issues", []),
            "summary": vlm.get("summary", ""),
            "parse_error": vlm.get("parse_error", False),
        },
        "regex_worker_output": {
            "status": regex.get("status", "UNKNOWN"),
            "issues_found": regex.get("issues", []),
            "warnings": regex.get("warnings", []),
        },
        "rag_worker_output": {
            "total_flags": len(rag),
            "critical_flags": [{"rule_id": f["rule_id"], "title": f["title"],
                                  "citation": f["citation"], "summary": f.get("summary", "")}
                                 for f in crit_flags],
            "high_flags":     [{"rule_id": f["rule_id"], "title": f["title"],
                                  "citation": f["citation"]}
                                 for f in high_flags],
        },
        "document_fields": {
            "product_category": fields.get("product_category", "unknown"),
            "hs_codes": fields.get("hs_codes", []),
            "iec_present": fields.get("iec_present", False),
            "requires_scomet": fields.get("requires_scomet", False),
            "importer_country": fields.get("importer_country", "unknown"),
        }
    }
    return f"Here are the three worker reports for your audit:\n\n{json.dumps(context, indent=2)}"


def _determine_status_fallback(state: dict) -> str:
    """Rule-based fallback status if Supervisor LLM is unavailable."""
    vlm_status   = state.get("vlm_result", {}).get("status", "PASSED")
    regex_status = state.get("regex_result", {}).get("status", "PASSED")
    rag_flags    = state.get("rag_result", [])
    has_critical = any(f["severity"] == "CRITICAL" for f in rag_flags)

    if vlm_status == "REJECTED" or regex_status == "REJECTED" or has_critical:
        return "REJECTED"
    if rag_flags:
        return "NEEDS_REVIEW"
    return "PASSED"


def supervisor_node(state: dict) -> dict:
    """
    LangGraph node: Qwen3-30B-A3B Supervisor.

    Reads:   state["vlm_result"], state["regex_result"],
             state["rag_result"], state["document_fields"]
    Writes:  state["supervisor_result"], state["final_status"]
    """
    logger.info("[Supervisor] Building context from worker outputs...")
    user_message = _build_user_message(state)

    # Try calling the vLLM supervisor
    try:
        from openai import OpenAI
        client = OpenAI(api_key="EMPTY", base_url=SUPERVISOR_URL)

        logger.info(f"[Supervisor] Calling {SUPERVISOR_MODEL}...")
        response = client.chat.completions.create(
            model=SUPERVISOR_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.1,      # near-deterministic for legal reasoning
            max_tokens=1024,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON from response (strip markdown fences if present)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)

        final_status = parsed.get("final_status", _determine_status_fallback(state))
        logger.info(f"[Supervisor] Verdict: {final_status} (confidence={parsed.get('confidence','?')})")

        return {
            "supervisor_result": parsed,
            "final_status": final_status,
            "supervisor_available": True,
        }

    except Exception as e:
        logger.warning(f"[Supervisor] vLLM unavailable ({e}), using rule-based fallback.")
        fallback_status = _determine_status_fallback(state)

        # Build a minimal fallback report from available data
        vlm_issues   = state.get("vlm_result", {}).get("issues", [])
        regex_issues = state.get("regex_result", {}).get("issues", [])
        rag_flags    = state.get("rag_result", [])
        all_issues   = vlm_issues + regex_issues

        if fallback_status == "REJECTED":
            audit = (f"The document set has been REJECTED due to {len(all_issues)} discrepancy(ies) "
                     f"and {sum(1 for f in rag_flags if f['severity']=='CRITICAL')} critical regulatory flag(s).")
            risk = ("Review the specific issues and regulatory flags below. "
                    "Supervisor AI is offline — manual review of penalty exposure is required.")
        elif fallback_status == "NEEDS_REVIEW":
            audit = f"The document set requires manual review. {len(rag_flags)} regulatory consideration(s) flagged."
            risk = None
        else:
            audit = "All automated checks passed. No discrepancies or regulatory flags detected."
            risk = None

        return {
            "supervisor_result": {
                "final_status": fallback_status,
                "confidence": "LOW",
                "audit_report": audit,
                "risk_summary": risk,
                "key_issues": [i.get("type","") for i in all_issues],
                "supervisor_reasoning": "Supervisor LLM unavailable. Rule-based fallback applied.",
            },
            "final_status": fallback_status,
            "supervisor_available": False,
        }
