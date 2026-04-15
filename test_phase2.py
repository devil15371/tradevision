"""
Phase 2 Test Suite
Tests: LLM extractor, RAG checker, and full end-to-end PDF pipeline.

Run: python3 test_phase2.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extraction.extract import extract_document
from extraction.compare import compare_invoice_packing_list
from models.llm_extractor import LLMExtractor
from models.rag_checker import RAGChecker


PASS = "✅ PASS"
FAIL = "❌ FAIL"


def print_header(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


# ─────────────────────────────────────────────
# Part 1: LLM Extractor Tests
# ─────────────────────────────────────────────

def test_extractor():
    print_header("Part 1: LLM Field Extractor")
    extractor = LLMExtractor()
    results = []

    # Test 1a: Detect garment invoice
    t = (
        "COMMERCIAL INVOICE. Invoice No: INV-2024-00142. "
        "Men's Denim Trousers, HS Code: 620342. Buyer: Dubai, UAE. "
        "Gross Weight: 320 kg. Total Invoice Value: USD 14550.00. IEC Code: 0815099123."
    )
    fields = extractor.extract(t)
    ok = (
        fields["document_type"] == "commercial_invoice"
        and fields["product_category"] == "garments"
        and fields["importer_country"] == "UAE"
        and fields["requires_rcmc"] is True
        and "620342" in fields["hs_codes"]
    )
    print(f"{PASS if ok else FAIL} — Garment invoice: "
          f"doc_type={fields['document_type']}, category={fields['product_category']}, "
          f"country={fields['importer_country']}, rcmc={fields['requires_rcmc']}")
    results.append(ok)

    # Test 1b: Detect pharma invoice with SCOMET risk (wrong HS prefix, chemicals)
    t2 = (
        "COMMERCIAL INVOICE. Invoice No: INV-2024-00199. "
        "Paracetamol 500mg Tablets, HS Code: 300490. "
        "Buyer: MedSupply GmbH, Frankfurt, Germany. "
        "Gross Weight: 180 kg. Total Value USD 21500."
    )
    fields2 = extractor.extract(t2)
    ok2 = (
        fields2["product_category"] == "pharma"
        and fields2["importer_country"] == "Germany"
        and "300490" in fields2["hs_codes"]
    )
    print(f"{PASS if ok2 else FAIL} — Pharma invoice: "
          f"category={fields2['product_category']}, country={fields2['importer_country']}, "
          f"hs_codes={fields2['hs_codes']}")
    results.append(ok2)

    # Test 1c: Detect packing list document type
    t3 = "PACKING LIST. Packing List No: PL-2024-001. Net Wt: 305 kg. Gross Wt: 320 kg. Cartons: 40."
    fields3 = extractor.extract(t3)
    ok3 = fields3["document_type"] == "packing_list"
    print(f"{PASS if ok3 else FAIL} — Packing list doc type: {fields3['document_type']}")
    results.append(ok3)

    # Test 1d: IEC detection
    t4 = "Exporter IEC: 0815099123. Goods: Handicraft items."
    fields4 = extractor.extract(t4)
    ok4 = fields4["iec_present"] is True and fields4["product_category"] == "handicrafts"
    print(f"{PASS if ok4 else FAIL} — IEC present={fields4['iec_present']}, "
          f"category={fields4['product_category']}")
    results.append(ok4)

    return results


# ─────────────────────────────────────────────
# Part 2: RAG Checker Tests
# ─────────────────────────────────────────────

def test_rag_checker():
    print_header("Part 2: RAG Checker")
    checker = RAGChecker()
    results = []

    # Test 2a: Garment export should flag AEPC RCMC regulation
    flags = checker.check(
        doc_text="Men's Cotton Shirts and Denim Trousers export from India to UAE.",
        hs_codes=["620520", "620342"],
        product_category="garments",
    )
    flag_ids = [f["rule_id"] for f in flags]
    ok = "DGFT-FTP2023-GARMENTS-AEPC" in flag_ids
    print(f"{PASS if ok else FAIL} — Garment: AEPC RCMC flag raised | flags: {flag_ids[:4]}")
    results.append(ok)

    # Test 2b: Pharma export with HS mismatch should flag penalty regulation
    flags2 = checker.check(
        doc_text="Pharmaceutical tablets export from India to Germany.",
        hs_codes=["300490"],
        product_category="pharma",
        triggered_issues=["WEIGHT_MISMATCH", "HS_CODE_MISMATCH"],
    )
    flag_ids2 = [f["rule_id"] for f in flags2]
    ok2 = (
        "CUSTOMS-ACT-1962-SEC111m" in flag_ids2
        and "DGFT-FTP2023-4.42" in flag_ids2
    )
    print(f"{PASS if ok2 else FAIL} — Pharma+mismatch: penalty+pharma flags raised "
          f"| flags: {flag_ids2[:5]}")
    results.append(ok2)

    # Test 2c: IEC regulation always included
    flags3 = checker.check(doc_text="Generic export document.", hs_codes=[])
    flag_ids3 = [f["rule_id"] for f in flags3]
    ok3 = "DGFT-FTP2023-2.05" in flag_ids3
    print(f"{PASS if ok3 else FAIL} — IEC rule always present | flags: {flag_ids3[:3]}")
    results.append(ok3)

    # Test 2d: CRITICAL severity always sorted first
    flags4 = checker.check(
        doc_text="Pharmaceutical tablets.",
        hs_codes=["300490"],
        triggered_issues=["WEIGHT_MISMATCH", "HS_CODE_MISMATCH"],
    )
    top_severity = flags4[0]["severity"] if flags4 else "NONE"
    ok4 = top_severity in ("CRITICAL", "HIGH")
    print(f"{PASS if ok4 else FAIL} — Severity sorting: top flag is {top_severity}")
    results.append(ok4)

    return results


# ─────────────────────────────────────────────
# Part 3: Full End-to-End PDF Pipeline
# ─────────────────────────────────────────────

def test_end_to_end():
    print_header("Part 3: End-to-End PDF Pipeline")
    extractor = LLMExtractor()
    checker = RAGChecker()
    results = []

    for label, inv_path, pl_path, expected_status in [
        ("Garment (matching)",  "data/invoice_1_correct.pdf",  "data/packing_list_1_correct.pdf", "PASSED"),
        ("Pharma (errors)",     "data/invoice_2_errors.pdf",   "data/packing_list_2_errors.pdf",  "REJECTED"),
    ]:
        inv_data = extract_document(inv_path)
        pl_data  = extract_document(pl_path)

        # Phase 1 comparison
        comparison = compare_invoice_packing_list(inv_data["text"], pl_data["text"])

        # Phase 2 extraction + RAG
        fields = extractor.extract(inv_data["text"])
        reg_flags = checker.check(
            doc_text=inv_data["text"],
            hs_codes=fields["hs_codes"],
            product_category=fields["product_category"],
            triggered_issues=[i["type"] for i in comparison["issues"]],
        )

        ok = comparison["status"] == expected_status
        print(f"\n{PASS if ok else FAIL} — {label}")
        print(f"  Phase 1 status : {comparison['status']} "
              f"({len(comparison['issues'])} issues)")
        print(f"  Fields detected: category={fields['product_category']}, "
              f"country={fields['importer_country']}, "
              f"hs_codes={fields['hs_codes'][:3]}")
        print(f"  Regulatory flags: {len(reg_flags)} rules triggered")
        for f in reg_flags[:3]:
            print(f"    [{f['severity']}] {f['rule_id']}: {f['title'][:55]}")
        results.append(ok)

    return results


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

if __name__ == "__main__":
    all_results = []

    r1 = test_extractor()
    r2 = test_rag_checker()
    r3 = test_end_to_end()

    all_results = r1 + r2 + r3
    passed = sum(all_results)
    total  = len(all_results)

    print(f"\n{'='*55}")
    print(f"  PHASE 2 TEST RESULTS: {passed}/{total} passed")
    print(f"{'='*55}")
    if passed == total:
        print("🎉 All Phase 2 tests passed! Ready for /check_full endpoint.")
    else:
        failed = [i+1 for i, r in enumerate(all_results) if not r]
        print(f"⚠️  Failed tests: {failed}")
