"""
RAG Checker — Phase 2
Loads regulations_kb.json, embeds regulation texts using sentence-transformers,
builds a FAISS index, and queries relevant regulations for any document.

Usage:
    checker = RAGChecker()
    results = checker.check(doc_text, hs_codes=["620342"], product_category="garments")
"""

import json
import os
import numpy as np

KB_PATH = os.path.join(os.path.dirname(__file__), "regulations_kb.json")


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Simple cosine similarity without FAISS dependency."""
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return a_norm @ b_norm.T


class RAGChecker:
    def __init__(self, kb_path: str = KB_PATH):
        self.kb_path = kb_path
        self._regulations = []
        self._embeddings = None
        self._model = None
        self._load_kb()
        self._build_index()

    # ─────────────────────────────────────────────
    # Setup
    # ─────────────────────────────────────────────

    def _load_kb(self):
        with open(self.kb_path, "r") as f:
            data = json.load(f)
        self._regulations = data["regulations"]
        print(f"[RAGChecker] Loaded {len(self._regulations)} regulations from KB.")

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print("[RAGChecker] Loading embedding model (all-MiniLM-L6-v2)...")
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            print("[RAGChecker] Model loaded.")
        return self._model

    def _build_index(self):
        """Build embedding index for all regulation texts."""
        model = self._get_model()
        texts = [
            f"{reg['title']}. {reg['text']} Keywords: {', '.join(reg['keywords'])}"
            for reg in self._regulations
        ]
        self._embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        print(f"[RAGChecker] Indexed {len(self._embeddings)} regulation embeddings.")

    # ─────────────────────────────────────────────
    # Query
    # ─────────────────────────────────────────────

    def _semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Find top-k most semantically similar regulations for a query."""
        model = self._get_model()
        q_emb = model.encode([query], convert_to_numpy=True)
        sims = _cosine_similarity(q_emb, self._embeddings)[0]
        top_indices = np.argsort(sims)[::-1][:top_k]
        results = []
        for idx in top_indices:
            reg = self._regulations[idx].copy()
            reg["similarity_score"] = float(sims[idx])
            results.append(reg)
        return results

    def _hs_code_match(self, hs_codes: list[str]) -> list[dict]:
        """Find regulations that explicitly cover the given HS codes."""
        matched = []
        for reg in self._regulations:
            for hs in hs_codes:
                # match if reg hs_codes_affected contains the code or a prefix
                if any(hs.startswith(r_hs) or r_hs.startswith(hs[:4])
                       for r_hs in reg.get("hs_codes_affected", [])):
                    if reg not in matched:
                        matched.append(reg)
        return matched

    # ─────────────────────────────────────────────
    # Main Check
    # ─────────────────────────────────────────────

    def check(
        self,
        doc_text: str,
        hs_codes: list[str] | None = None,
        product_category: str | None = None,
        triggered_issues: list[str] | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.30,
    ) -> list[dict]:
        """
        Run RAG check on document text.

        Args:
            doc_text: Extracted text from the trade document
            hs_codes: List of HS codes found in the document
            product_category: e.g. 'garments', 'pharma', 'handicrafts'
            triggered_issues: List of issue types from Phase 1 regex (e.g. ['WEIGHT_MISMATCH'])
            top_k: Max number of semantically relevant regulations to retrieve
            similarity_threshold: Min cosine similarity to include a result

        Returns:
            List of regulatory flags (dicts)
        """
        hs_codes = hs_codes or []
        triggered_issues = triggered_issues or []
        flags = []
        seen_ids = set()

        # 1 — Always-check regulations (IEC, shipping bill, origin, FEMA)
        for reg in self._regulations:
            if reg.get("check_trigger") == "always" and reg["id"] not in seen_ids:
                flags.append(self._make_flag(reg, "REGULATORY_REQUIREMENT"))
                seen_ids.add(reg["id"])

        # 2 — HS code triggered regulations
        if hs_codes:
            for reg in self._hs_code_match(hs_codes):
                if reg["id"] not in seen_ids:
                    flags.append(self._make_flag(reg, "HS_CODE_REGULATORY_FLAG"))
                    seen_ids.add(reg["id"])

        # 3 — Issue-triggered regulations
        if "WEIGHT_MISMATCH" in triggered_issues or "HS_CODE_MISMATCH" in triggered_issues:
            for reg in self._regulations:
                if reg.get("check_trigger") in ("weight_mismatch", "hs_code_mismatch"):
                    if reg["id"] not in seen_ids:
                        flags.append(self._make_flag(reg, "MISMATCH_PENALTY_RISK"))
                        seen_ids.add(reg["id"])

        # 4 — Semantic search on full document text
        if doc_text.strip():
            semantic_hits = self._semantic_search(doc_text, top_k=top_k)
            for reg in semantic_hits:
                if (reg["id"] not in seen_ids
                        and reg["similarity_score"] >= similarity_threshold):
                    flags.append(self._make_flag(reg, "SEMANTIC_MATCH", reg["similarity_score"]))
                    seen_ids.add(reg["id"])

        # Sort by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        flags.sort(key=lambda x: severity_order.get(x["severity"], 9))

        return flags

    @staticmethod
    def _make_flag(reg: dict, match_type: str, score: float = 1.0) -> dict:
        return {
            "rule_id": reg["id"],
            "title": reg["title"],
            "category": reg["category"],
            "severity": reg["severity"],
            "citation": reg["citation"],
            "match_type": match_type,
            "relevance_score": round(score, 3),
            "summary": reg["text"][:300] + "..." if len(reg["text"]) > 300 else reg["text"],
        }


# ─────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    checker = RAGChecker()

    print("\n=== Test 1: Garment export (HS 620342) ===")
    flags = checker.check(
        doc_text="Commercial invoice for men's denim trousers. Exporter: Shree Fabrics Pvt Ltd. Buyer: UAE.",
        hs_codes=["620342"],
        product_category="garments",
    )
    for f in flags[:5]:
        print(f"  [{f['severity']}] {f['rule_id']}: {f['title']}")

    print("\n=== Test 2: Pharma export with HS mismatch ===")
    flags2 = checker.check(
        doc_text="Commercial invoice for Paracetamol 500mg tablets. HS Code: 300490.",
        hs_codes=["300490"],
        product_category="pharma",
        triggered_issues=["WEIGHT_MISMATCH", "HS_CODE_MISMATCH"],
    )
    for f in flags2[:6]:
        print(f"  [{f['severity']}] {f['rule_id']}: {f['title']}")
