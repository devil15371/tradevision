import json
import re


def extract_numbers_from_text(text):
    """Pull all numbers from document text"""
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
    return [float(n) for n in numbers]


def extract_weights_from_text(text):
    """
    Find the primary (gross/total) weight from a document.
    Prioritises lines labelled 'gross weight' or 'total weight' to avoid
    summing up individual row weights from tables.
    Falls back to any weight mention if no labelled line is found.
    """
    lower = text.lower()

    # Priority 1: labelled gross / total weight line
    labelled = re.findall(
        r'(?:gross\s+weight|total\s+weight|g\.?\s*wt\.?)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram|kilograms)',
        lower
    )
    if labelled:
        return [float(w) for w in labelled]

    # Priority 2: any weight mention (fallback)
    all_weights = re.findall(r'(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram|kilograms)', lower)
    return [float(w) for w in all_weights]


def extract_hs_codes_from_text(text):
    """Find HS codes — they follow specific patterns"""
    # HS codes are 6–8 digit numbers (6-digit international, up to 8-digit in India).
    # Intentionally excludes 10-digit IEC/CIN codes.
    hs_pattern = r'\b(\d{6,8})\b'
    codes = re.findall(hs_pattern, text)
    return codes


def compare_invoice_packing_list(invoice_text, packing_list_text):
    """
    Basic comparison between invoice and packing list.
    Returns list of potential issues found.
    """
    issues = []
    warnings = []

    # --- Weight comparison ---
    invoice_weights = extract_weights_from_text(invoice_text)
    packing_weights = extract_weights_from_text(packing_list_text)

    if not invoice_weights:
        warnings.append("No weight information found in invoice")
    if not packing_weights:
        warnings.append("No weight information found in packing list")

    if invoice_weights and packing_weights:
        inv_total = sum(invoice_weights)
        pack_total = sum(packing_weights)
        difference = abs(inv_total - pack_total)

        if difference > 0.01:
            issues.append({
                "type": "WEIGHT_MISMATCH",
                "severity": "HIGH",
                "detail": (
                    f"Invoice weight: {inv_total}kg, "
                    f"Packing list weight: {pack_total}kg, "
                    f"Difference: {difference}kg"
                )
            })

    # --- HS Code comparison ---
    invoice_hs = set(extract_hs_codes_from_text(invoice_text))
    packing_hs = set(extract_hs_codes_from_text(packing_list_text))

    hs_only_in_invoice = invoice_hs - packing_hs
    hs_only_in_packing = packing_hs - invoice_hs

    if hs_only_in_invoice:
        issues.append({
            "type": "HS_CODE_MISMATCH",
            "severity": "HIGH",
            "detail": f"HS codes in invoice but not packing list: {hs_only_in_invoice}"
        })

    if hs_only_in_packing:
        issues.append({
            "type": "HS_CODE_MISMATCH",
            "severity": "HIGH",
            "detail": f"HS codes in packing list but not invoice: {hs_only_in_packing}"
        })

    # --- Final verdict ---
    if issues:
        status = "REJECTED"
    elif warnings:
        status = "NEEDS_REVIEW"
    else:
        status = "PASSED"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "summary": f"Found {len(issues)} issues and {len(warnings)} warnings"
    }


# test it
if __name__ == "__main__":
    sample_invoice = "Total weight: 25 kg. HS Code: 620342. Value: USD 500."
    sample_packing = "Total weight: 27 kg. HS Code: 620342. Boxes: 10."

    result = compare_invoice_packing_list(sample_invoice, sample_packing)
    print(json.dumps(result, indent=2))
