"""
LLM Field Extractor — Phase 2
Pure regex + keyword matching. No model download needed.
Extracts structured fields from raw PDF text for use by the RAG checker.

Usage:
    extractor = LLMExtractor()
    fields = extractor.extract(text)
"""

import re


# ─────────────────────────────────────────────
# Field Extraction Rules
# ─────────────────────────────────────────────

DOCUMENT_TYPE_PATTERNS = {
    "commercial_invoice": [
        r"commercial\s+invoice", r"invoice\s+no", r"inv[-\s]?\d",
        r"invoice\s+date", r"invoice\s+value"
    ],
    "packing_list": [
        r"packing\s+list", r"packing\s+list\s+no", r"pl[-\s]?\d",
        r"no\.\s+of\s+(carton|box|package)", r"gross\s+wt", r"net\s+wt"
    ],
    "bill_of_lading": [
        r"bill\s+of\s+lading", r"b/l\s+no", r"bl\s+no",
        r"ocean\s+bill", r"shipper", r"consignee", r"notify\s+party",
        r"vessel", r"voyage", r"port\s+of\s+(loading|discharge)"
    ],
    "airway_bill": [
        r"air\s+waybill", r"awb", r"air\s+consignment", r"flight\s+no"
    ],
    "certificate_of_origin": [
        r"certificate\s+of\s+origin", r"country\s+of\s+origin", r"co[-\s]?o\b"
    ]
}

PRODUCT_CATEGORY_PATTERNS = {
    "garments": [
        r"\b(garment|readymade|apparel|shirt|trouser|kurta|denim|blouse|jacket|dress|textile|fabric|made.up)\b"
    ],
    "pharma": [
        r"\b(pharma|pharmaceutical|medicine|drug|tablet|capsule|injection|api|active pharmaceutical|paracetamol|ibuprofen|amoxicillin|insulin|syrup|ointment)\b"
    ],
    "electronics": [
        r"\b(electronic|semiconductor|microprocessor|pcb|printed circuit|led|battery|charger|laptop|mobile|phone|computer)\b"
    ],
    "food": [
        r"\b(food|edible|spice|rice|wheat|sugar|tea|coffee|biscuit|chocolate|sauce|pickle|organic|grain|cereal|beverage|juice)\b"
    ],
    "handicrafts": [
        r"\b(handicraft|brass|woodwork|pottery|carpet|handloom|embroidery|jewellery|gemstone|artefact|artifact|artisan|craft)\b"
    ],
    "chemicals": [
        r"\b(chemical|solvent|acid|reagent|compound|organic chemical|inorganic|polymer|resin|catalyst)\b"
    ],
    "metals": [
        r"\b(steel|iron|aluminium|aluminum|copper|zinc|alloy|ingot|billet|scrap metal|metal product)\b"
    ],
    "machinery": [
        r"\b(machine|machinery|equipment|pump|compressor|turbine|motor|generator|valve|instrument)\b"
    ]
}

COUNTRY_PATTERNS = {
    "UAE": [r"\b(uae|united arab emirates|dubai|abu dhabi|jebel ali|sharjah)\b"],
    "USA": [r"\b(usa|united states|america|new york|los angeles|chicago)\b"],
    "Germany": [r"\b(germany|deutschland|frankfurt|hamburg|berlin|munich)\b"],
    "UK": [r"\b(united kingdom|uk|britain|england|london|birmingham)\b"],
    "China": [r"\b(china|prc|shanghai|beijing|guangzhou|shenzhen)\b"],
    "Bangladesh": [r"\b(bangladesh|dhaka|chittagong)\b"],
    "Sri Lanka": [r"\b(sri lanka|colombo|ceylon)\b"],
    "Pakistan": [r"\b(pakistan|karachi|lahore)\b"],
    "Myanmar": [r"\b(myanmar|burma|rangoon|yangon)\b"],
    "Nepal": [r"\b(nepal|kathmandu)\b"],
    "Australia": [r"\b(australia|sydney|melbourne|canberra)\b"],
    "Japan": [r"\b(japan|tokyo|osaka|nagoya)\b"],
    "South Korea": [r"\b(south korea|korea|seoul|busan|incheon)\b"],
    "Singapore": [r"\b(singapore)\b"],
    "Brazil": [r"\b(brazil|brasil|sao paulo|rio de janeiro)\b"],
}

# SCOMET-relevant HS code prefixes (first 4 digits)
SCOMET_HS_PREFIXES = {
    "2812", "2850", "2903", "2904", "2921", "2922", "2931", "2933",  # Cat 1 chemicals
    "7202", "7218", "8112", "8104", "2845", "6815",                   # Cat 3 materials
    "8471", "8473", "8541", "8542", "8543", "8517", "8525", "8526",   # Cat 7 electronics
    "9301", "9302", "9303", "9304", "9305", "9306", "9307",           # Cat 6 weapons
    "8802", "8803", "8804", "8805",                                    # Cat 9 aerospace
}

PHARMA_HS_PREFIXES = {"2801", "2802", "2901", "2902", "2903", "3001", "3002", "3003", "3004", "3005", "3006"}
GARMENT_HS_PREFIXES = {"6101", "6102", "6103", "6104", "6105", "6106", "6107", "6108", "6109",
                        "6110", "6201", "6202", "6203", "6204", "6205", "6206", "6207", "6208", "6209",
                        "6210", "6211", "6212", "6213", "6214", "6215", "6216", "6217"}
FOOD_HS_PREFIXES = {"0401", "0402", "0403", "0404", "0901", "0902", "1006", "1701", "1801", "1901", "2009"}


# ─────────────────────────────────────────────
# Extractor Class
# ─────────────────────────────────────────────

class LLMExtractor:
    """
    Extracts structured fields from raw trade document text.
    Pure regex + keyword matching — no model required.
    """

    def extract(self, text: str) -> dict:
        lower = text.lower()
        hs_codes = self._extract_hs_codes(text)

        return {
            "document_type":     self._detect_document_type(lower),
            "product_category":  self._detect_product_category(lower, hs_codes),
            "exporter_country":  "India",   # always India for this product
            "importer_country":  self._detect_importer_country(lower),
            "hs_codes":          hs_codes,
            "requires_scomet":   self._check_scomet(hs_codes, lower),
            "requires_rcmc":     self._check_rcmc(hs_codes, lower),
            "requires_fssai":    self._check_fssai(hs_codes, lower),
            "iec_present":       self._check_iec_present(text),
            "invoice_value_usd": self._extract_usd_value(text),
        }

    # ─────────────────────────────────────────────
    # Individual Field Extractors
    # ─────────────────────────────────────────────

    def _detect_document_type(self, lower: str) -> str:
        scores = {}
        for doc_type, patterns in DOCUMENT_TYPE_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, lower))
            if score > 0:
                scores[doc_type] = score
        if not scores:
            return "unknown"
        return max(scores, key=scores.get)

    def _detect_product_category(self, lower: str, hs_codes: list) -> str:
        # HS-code based detection first (more reliable)
        for hs in hs_codes:
            prefix = hs[:4]
            if prefix in PHARMA_HS_PREFIXES:
                return "pharma"
            if prefix in GARMENT_HS_PREFIXES:
                return "garments"
            if prefix in FOOD_HS_PREFIXES:
                return "food"

        # Keyword fallback
        scores = {}
        for category, patterns in PRODUCT_CATEGORY_PATTERNS.items():
            score = sum(len(re.findall(p, lower)) for p in patterns)
            if score > 0:
                scores[category] = score
        if not scores:
            return "general"
        return max(scores, key=scores.get)

    def _detect_importer_country(self, lower: str) -> str:
        for country, patterns in COUNTRY_PATTERNS.items():
            for p in patterns:
                if re.search(p, lower):
                    return country
        return "unknown"

    def _extract_hs_codes(self, text: str) -> list:
        """Extract 6–8 digit HS codes, excluding 10-digit IEC/PAN etc."""
        codes = re.findall(r'\b(\d{6,8})\b', text)
        return list(dict.fromkeys(codes))  # deduplicate preserving order

    def _check_scomet(self, hs_codes: list, lower: str) -> bool:
        # keyword check
        scomet_keywords = ["scomet", "dual use", "dual-use", "export authorisation", "end user certificate"]
        if any(kw in lower for kw in scomet_keywords):
            return True
        # HS prefix check
        for hs in hs_codes:
            if hs[:4] in SCOMET_HS_PREFIXES:
                return True
        return False

    def _check_rcmc(self, hs_codes: list, lower: str) -> bool:
        """Returns True if RCMC is likely required based on product type."""
        rcmc_keywords = ["rcmc", "export promotion council", "aepc", "pharmexcil", "epch",
                         "advance authorisation", "epcg", "status holder"]
        if any(kw in lower for kw in rcmc_keywords):
            return True
        # garment or pharma HS codes → likely need RCMC for FTP benefits
        for hs in hs_codes:
            prefix = hs[:4]
            if prefix in GARMENT_HS_PREFIXES or prefix in PHARMA_HS_PREFIXES:
                return True
        return False

    def _check_fssai(self, hs_codes: list, lower: str) -> bool:
        if "fssai" in lower or "food safety" in lower:
            return True
        for hs in hs_codes:
            if hs[:4] in FOOD_HS_PREFIXES:
                return True
        return False

    def _check_iec_present(self, text: str) -> bool:
        """Check if a 10-digit IEC code pattern is present."""
        return bool(re.search(r'\b\d{10}\b', text))

    def _extract_usd_value(self, text: str) -> float | None:
        """Extract total invoice value in USD."""
        patterns = [
            r'(?:total|invoice)[\s\w]*value[\s:]*usd[\s]*([0-9,]+(?:\.\d+)?)',
            r'usd[\s]*([0-9,]+(?:\.\d+)?)',
            r'\$[\s]*([0-9,]+(?:\.\d+)?)',
        ]
        for p in patterns:
            m = re.search(p, text.lower())
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
        return None


# ─────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json

    extractor = LLMExtractor()

    print("=== Test 1: Garment Invoice ===")
    t1 = """COMMERCIAL INVOICE
    Invoice No: INV-2024-00142. Exporter: Shree Fabrics Pvt Ltd, Surat.
    Buyer: Al-Ansar Trading LLC, Dubai, UAE.
    Men's Denim Trousers, HS Code: 620342. Men's Cotton Shirts HS Code 620520.
    Gross Weight: 320 kg. Total Invoice Value: USD 14,550.00. IEC Code: 0815099123."""
    print(json.dumps(extractor.extract(t1), indent=2))

    print("\n=== Test 2: Pharma Invoice ===")
    t2 = """COMMERCIAL INVOICE
    Invoice No: INV-2024-00199. Exporter: Krishna Pharma Exports, Hyderabad.
    Buyer: MedSupply GmbH, Frankfurt, Germany.
    Paracetamol 500mg Tablets, HS Code: 300490. Ibuprofen 400mg Tablets, HS Code: 300490.
    Gross Weight: 180 kg. Total Value USD 21,500.00."""
    print(json.dumps(extractor.extract(t2), indent=2))
