"""
TradeVision test suite — Day 6/7 verification tests.
Run: python3 test_compare.py
"""
from extraction.compare import compare_invoice_packing_list
import json


def run_test(name, invoice, packing, expected_status):
    result = compare_invoice_packing_list(invoice, packing)
    status = result["status"]
    passed = "✅ PASS" if status == expected_status else f"❌ FAIL (got {status})"
    print(f"{passed} — {name}")
    if status != expected_status:
        print(f"  Detail: {json.dumps(result, indent=4)}")
    return status == expected_status


if __name__ == "__main__":
    print("=" * 50)
    print("TradeVision Compliance Engine — Test Suite")
    print("=" * 50)

    results = []

    # Test 1 — Perfect match, should PASS
    results.append(run_test(
        "Perfect match",
        invoice="Weight: 25 kg. HS Code: 620342.",
        packing="Weight: 25 kg. HS Code: 620342.",
        expected_status="PASSED"
    ))

    # Test 2 — Weight mismatch, should REJECT
    results.append(run_test(
        "Weight mismatch",
        invoice="Weight: 25 kg. HS Code: 620342.",
        packing="Weight: 30 kg. HS Code: 620342.",
        expected_status="REJECTED"
    ))

    # Test 3 — HS code mismatch, should REJECT
    results.append(run_test(
        "HS code mismatch",
        invoice="Weight: 25 kg. HS Code: 620342.",
        packing="Weight: 25 kg. HS Code: 999999.",
        expected_status="REJECTED"
    ))

    # Test 4 — Missing weights in both, should NEEDS_REVIEW
    results.append(run_test(
        "No weight info in both docs",
        invoice="Invoice for garments. HS Code: 620342.",
        packing="Packing list. HS Code: 620342.",
        expected_status="NEEDS_REVIEW"
    ))

    # Test 5 — Both weight AND HS mismatch
    results.append(run_test(
        "Weight + HS code both mismatch",
        invoice="Weight: 100 kg. HS Code: 620342.",
        packing="Weight: 50 kg. HS Code: 850433.",
        expected_status="REJECTED"
    ))

    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    if passed == total:
        print("🎉 All tests passed! Compliance engine is working correctly.")
    else:
        print("⚠️  Some tests failed. Review the output above.")
