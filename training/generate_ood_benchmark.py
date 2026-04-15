"""
OOD Benchmark Generator
Generates 50 out-of-distribution document pairs using new exporters,
importers, products, and layout variations never seen in training data.

Run: python3 training/generate_ood_benchmark.py
Output: data/ood_benchmark/ with labels.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpdf import FPDF
import json
import random


# ── OOD entity lists — entirely new, not in training data ─────────
OOD_EXPORTERS = [
    {"name": "Nagpur Agro Exports Pvt Ltd",   "city": "Nagpur",     "state": "Maharashtra",     "iec": "0916011111"},
    {"name": "Coimbatore Precision Tools Ltd", "city": "Coimbatore", "state": "Tamil Nadu",      "iec": "0716022222"},
    {"name": "Bhubaneswar Handicrafts Inc",    "city": "Bhubaneswar","state": "Odisha",          "iec": "0616033333"},
    {"name": "Raipur Steel Products Ltd",      "city": "Raipur",     "state": "Chhattisgarh",    "iec": "0816044444"},
    {"name": "Guwahati Tea Exporters Co",      "city": "Guwahati",   "state": "Assam",           "iec": "0316055555"},
]

OOD_IMPORTERS = [
    {"name": "Seoul Trading Corp",         "city": "Seoul",       "country": "South Korea"},
    {"name": "Stockholm Imports AB",       "city": "Stockholm",   "country": "Sweden"},
    {"name": "Nairobi Import Partners",    "city": "Nairobi",     "country": "Kenya"},
    {"name": "Cairo Trade LLC",            "city": "Cairo",       "country": "Egypt"},
    {"name": "Sao Paulo Commerce SA",      "city": "Sao Paulo",   "country": "Brazil"},
]

OOD_PRODUCTS = [
    {"category": "gems",       "description": "Cut Diamond Stones (0.5 ct)",     "hs_code": "710231", "unit": "pieces", "unit_weight_kg": 0.01, "unit_value_usd": 500.00},
    {"category": "leather",    "description": "Finished Leather Upholstery Hide", "hs_code": "410791", "unit": "pieces", "unit_weight_kg": 3.0,  "unit_value_usd": 55.00},
    {"category": "chemicals",  "description": "Sodium Bicarbonate (Food Grade)",  "hs_code": "283620", "unit": "bags",   "unit_weight_kg": 25.0, "unit_value_usd": 18.00},
]

PORTS_OF_LOADING = [
    "Paradip Port, Odisha", "Tuticorin Sea Port", "Ennore Port, Tamil Nadu",
    "Haldia Dock Complex", "New Mangalore Port",
]

PAYMENT_TERMS = ["LC 60 days", "TT 45 days", "DA 90 days", "CAD", "Open Account 30 days"]
GROSS_LABELS  = ["Gross Weight:", "Total G.W.:", "Gross Wt. Total:"]
VALUE_LABELS  = ["Total CIF Value:", "Invoice Amount USD:", "CIF Total USD:"]


def _random_date():
    d, m = random.randint(1, 28), random.randint(1, 12)
    fmts = [f"{d:02d}/{m:02d}/2025", f"{m:02d}-{d:02d}-2025", f"2025.{m:02d}.{d:02d}"]
    return random.choice(fmts)


# ── Four distinct visual layouts ───────────────────────────────────

def _layout_a(pdf, title):
    """Left-aligned bold header — never used in training."""
    pdf.set_fill_color(0, 102, 102)
    pdf.rect(0, 0, 60, 30, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(5, 10)
    pdf.cell(50, 10, title)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(10, 35)


def _layout_b(pdf, title):
    """Double-ruled header."""
    pdf.line(5, 8, 205, 8)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(10, 10)
    pdf.cell(0, 8, title, align="C")
    pdf.line(5, 20, 205, 20)
    pdf.set_xy(10, 25)


def _layout_c(pdf, title):
    """Minimalist — just a small label, wide margins."""
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(15, 12)
    pdf.cell(0, 7, f"[ {title} ]")
    pdf.set_xy(15, 22)


def _layout_d(pdf, title):
    """Dense government-style with stamp box outline."""
    pdf.rect(5, 5, 200, 285)
    pdf.rect(5, 5, 200, 20)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_xy(10, 10)
    pdf.cell(0, 10, title.upper(), align="C")
    pdf.set_xy(10, 30)


LAYOUTS = [_layout_a, _layout_b, _layout_c, _layout_d]


def _render_parties(pdf, exp, imp):
    pdf.set_font("Helvetica", "B", 9)
    # Vary label wording — OOD from training
    pdf.cell(95, 5, "Seller / Exporter:", ln=False)
    pdf.cell(0, 5, "Buyer / Consignee:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(95, 5, exp["name"], ln=False)
    pdf.cell(0, 5, imp["name"], ln=True)
    pdf.cell(95, 5, f"{exp['city']}, {exp['state']}, India", ln=False)
    pdf.cell(0, 5, f"{imp['city']}, {imp['country']}", ln=True)
    pdf.cell(95, 5, f"Export Code: {exp['iec']}", ln=False)
    pdf.cell(0, 5, f"Dest. Country: {imp['country']}", ln=True)
    pdf.ln(4)


def _create_invoice(data, path):
    pdf = FPDF()
    pdf.add_page()
    LAYOUTS[data["layout_idx"]](pdf, "TAX INVOICE CUM EXPORT INVOICE")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Invoice Number: {data['doc_id']:04d}/EXP/2025", ln=True)
    pdf.cell(0, 5, f"Invoice Date: {data['date']}", ln=True)
    pdf.cell(0, 5, f"Port of Loading: {data['port_loading']}", ln=True)
    pdf.ln(3)
    _render_parties(pdf, data["exporter"], data["importer"])

    col_w = [60, 20, 20, 30, 25, 25]
    hdrs  = ["Item Description", "Qty", "Unit", "HS Tariff Code", "Gross Wt", "CIF Value"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(200, 210, 220)
    for h, w in zip(hdrs, col_w): pdf.cell(w, 6, h, border=1, fill=True)
    pdf.ln()

    inv, prod = data["invoice"], data["product"]
    pdf.set_font("Helvetica", "", 8)
    row = [prod["description"][:28], str(data["quantity"]), prod["unit"],
           inv["hs_code"], f"{inv['total_weight_kg']} KG", f"USD {inv['total_value_usd']:.2f}"]
    for val, w in zip(row, col_w): pdf.cell(w, 6, str(val), border=1)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, f"{random.choice(GROSS_LABELS)} {inv['total_weight_kg']} KGS", ln=True)
    pdf.cell(0, 5, f"{random.choice(VALUE_LABELS)} {inv['total_value_usd']:.2f}", ln=True)
    pdf.cell(0, 5, "Country of Origin: India", ln=True)
    pdf.cell(0, 5, f"Payment Terms: {random.choice(PAYMENT_TERMS)}", ln=True)
    pdf.output(path)


def _create_packing_list(data, path):
    pdf = FPDF()
    pdf.add_page()
    LAYOUTS[data["layout_idx"]](pdf, "PACKING LIST")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Packing List No: PL-{data['doc_id']:04d}/2025", ln=True)
    pdf.cell(0, 5, f"Against Invoice: {data['doc_id']:04d}/EXP/2025", ln=True)
    pdf.cell(0, 5, f"Date: {data['date']}", ln=True)
    pdf.ln(3)
    _render_parties(pdf, data["exporter"], data["importer"])

    col_w = [55, 18, 22, 28, 28, 14, 15]
    hdrs  = ["Description", "Qty", "HS Code", "Net Wt", "Gross Wt", "Pkgs", "CBM"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(200, 210, 220)
    for h, w in zip(hdrs, col_w): pdf.cell(w, 6, h, border=1, fill=True)
    pdf.ln()

    pl, prod = data["packing_list"], data["product"]
    net_wt   = round(pl["total_weight_kg"] * 0.91, 2)
    cbm      = round(random.uniform(0.3, 4.0), 3)
    pkgs     = max(1, data["quantity"] // random.randint(5, 15))

    pdf.set_font("Helvetica", "", 8)
    row = [prod["description"][:22], str(data["quantity"]), pl["hs_code"],
           f"{net_wt} KG", f"{pl['total_weight_kg']} KG", str(pkgs), str(cbm)]
    for val, w in zip(row, col_w): pdf.cell(w, 6, str(val), border=1)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, f"{random.choice(GROSS_LABELS)} {pl['total_weight_kg']} KGS", ln=True)
    pdf.cell(0, 5, f"Net Weight: {net_wt} KGS", ln=True)
    pdf.cell(0, 5, f"Total Packages: {pkgs} CTNS", ln=True)
    pdf.output(path)


def generate_ood_benchmark(n: int = 50, out_dir: str = "data/ood_benchmark"):
    os.makedirs(f"{out_dir}/invoices", exist_ok=True)
    os.makedirs(f"{out_dir}/packing_lists", exist_ok=True)
    random.seed(99)  # different seed from training

    labels = []
    stats  = {"clean": 0, "errors": 0}

    for i in range(n):
        inject_errors = (i % 2 == 1)

        exporter   = random.choice(OOD_EXPORTERS)
        importer   = random.choice(OOD_IMPORTERS)
        product    = random.choice(OOD_PRODUCTS)
        quantity   = random.randint(20, 500)
        layout_idx = i % 4  # cycle through all 4 OOD layouts

        total_weight = round(quantity * product["unit_weight_kg"], 2)
        total_value  = round(quantity * random.uniform(0.9, 1.1) * product["unit_value_usd"], 2)
        hs_code      = product["hs_code"]

        pl_weight, pl_hs_code = total_weight, hs_code
        errors_injected = []

        if inject_errors:
            error_types = random.sample(["weight", "hs_code"], k=random.randint(1, 2))
            if "weight" in error_types:
                pl_weight = round(total_weight * random.uniform(1.05, 1.35), 2)
                errors_injected.append({
                    "type": "WEIGHT_MISMATCH",
                    "invoice_weight": total_weight,
                    "packing_weight": pl_weight,
                })
            if "hs_code" in error_types:
                pl_hs_code = hs_code[:-2] + str(random.randint(10, 99)).zfill(2)
                errors_injected.append({
                    "type": "HS_CODE_MISMATCH",
                    "invoice_hs": hs_code,
                    "packing_hs": pl_hs_code,
                })

        data = {
            "doc_id": i + 1, "layout_idx": layout_idx,
            "date": _random_date(), "port_loading": random.choice(PORTS_OF_LOADING),
            "exporter": exporter, "importer": importer, "product": product,
            "quantity": quantity,
            "invoice":      {"total_weight_kg": total_weight, "total_value_usd": total_value, "hs_code": hs_code},
            "packing_list": {"total_weight_kg": pl_weight,   "hs_code": pl_hs_code},
        }

        inv_path = f"{out_dir}/invoices/ood_inv_{i+1:04d}.pdf"
        pl_path  = f"{out_dir}/packing_lists/ood_pl_{i+1:04d}.pdf"

        _create_invoice(data, inv_path)
        _create_packing_list(data, pl_path)

        expected_status = "REJECTED" if errors_injected else "PASSED"
        if inject_errors: stats["errors"] += 1
        else:             stats["clean"]  += 1

        labels.append({
            "id": i + 1,
            "invoice_path":      inv_path,
            "packing_list_path": pl_path,
            "layout": layout_idx,
            "expected_status":   expected_status,
            "errors":            errors_injected,
            "product_category": product["category"],
            "exporter": exporter["name"],
            "importer": importer["name"],
        })

        if (i + 1) % 10 == 0:
            print(f"  Generated {i+1}/{n} OOD pairs")

    with open(f"{out_dir}/labels.json", "w") as f:
        json.dump(labels, f, indent=2)

    print(f"\n✅ OOD Benchmark generated!")
    print(f"   Total : {n}  (clean={stats['clean']}, errors={stats['errors']})")
    print(f"   Layouts: 4 new styles (A/B/C/D, cycled)")
    print(f"   Exporters: {len(OOD_EXPORTERS)} new (not in training)")
    print(f"   Importers: {len(OOD_IMPORTERS)} new (not in training)")
    print(f"   Products : {len(OOD_PRODUCTS)} new categories")
    print(f"   Labels  : {out_dir}/labels.json")
    return labels


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    generate_ood_benchmark(n)
