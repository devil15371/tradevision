from fpdf import FPDF
import json
import random
import os

# ── Expanded entity lists ──────────────────────────────────────────
EXPORTERS = [
    {"name": "Sunrise Pharmaceuticals Pvt Ltd", "city": "Ahmedabad", "state": "Gujarat", "iec": "0814012345"},
    {"name": "Krishna Garments Export House", "city": "Tirupur", "state": "Tamil Nadu", "iec": "0714056789"},
    {"name": "Bharat Electronics Export Ltd", "city": "Bengaluru", "state": "Karnataka", "iec": "0514098765"},
    {"name": "Himalaya Handicrafts Co", "city": "Jaipur", "state": "Rajasthan", "iec": "0814023456"},
    {"name": "Spice Route Foods Pvt Ltd", "city": "Kochi", "state": "Kerala", "iec": "0614034567"},
    {"name": "Delhi Textiles Pvt Ltd", "city": "New Delhi", "state": "Delhi", "iec": "0514045678"},
    {"name": "Mumbai Chemicals Ltd", "city": "Mumbai", "state": "Maharashtra", "iec": "0314056789"},
    {"name": "Pune Auto Parts Export", "city": "Pune", "state": "Maharashtra", "iec": "0414067890"},
    {"name": "Ludhiana Woolen Mills", "city": "Ludhiana", "state": "Punjab", "iec": "0314078901"},
    {"name": "Surat Diamond Exports", "city": "Surat", "state": "Gujarat", "iec": "0814089012"},
]

IMPORTERS = [
    {"name": "Global Med GmbH", "city": "Berlin", "country": "Germany"},
    {"name": "Euro Textiles SA", "city": "Paris", "country": "France"},
    {"name": "US Tech Imports LLC", "city": "New York", "country": "USA"},
    {"name": "UK Trading Co Ltd", "city": "London", "country": "UK"},
    {"name": "Dubai Trade FZCO", "city": "Dubai", "country": "UAE"},
    {"name": "Singapore Pharma Pte Ltd", "city": "Singapore", "country": "Singapore"},
    {"name": "Tokyo Electronics KK", "city": "Tokyo", "country": "Japan"},
    {"name": "Sydney Imports Pty Ltd", "city": "Sydney", "country": "Australia"},
    {"name": "Toronto Trade Inc", "city": "Toronto", "country": "Canada"},
    {"name": "Amsterdam Foods BV", "city": "Amsterdam", "country": "Netherlands"},
]

PRODUCTS = [
    {"category": "pharma",      "description": "Pharmaceutical Tablets (Paracetamol 500mg)", "hs_code": "300490", "unit": "boxes",   "unit_weight_kg": 0.5,  "unit_value_usd": 12.50},
    {"category": "pharma",      "description": "Antibiotic Capsules (Amoxicillin 250mg)",    "hs_code": "300410", "unit": "boxes",   "unit_weight_kg": 0.4,  "unit_value_usd": 18.00},
    {"category": "pharma",      "description": "Vitamin C Tablets 500mg",                    "hs_code": "293625", "unit": "boxes",   "unit_weight_kg": 0.3,  "unit_value_usd": 8.50},
    {"category": "garments",    "description": "Cotton T-Shirts (Men's, Assorted Colors)",   "hs_code": "610910", "unit": "pieces",  "unit_weight_kg": 0.3,  "unit_value_usd": 8.00},
    {"category": "garments",    "description": "Denim Jeans Women's Blue",                   "hs_code": "620342", "unit": "pieces",  "unit_weight_kg": 0.6,  "unit_value_usd": 15.00},
    {"category": "garments",    "description": "Silk Sarees Handloom",                       "hs_code": "540740", "unit": "pieces",  "unit_weight_kg": 0.8,  "unit_value_usd": 45.00},
    {"category": "electronics", "description": "Printed Circuit Boards FR4 Double Layer",    "hs_code": "853400", "unit": "pieces",  "unit_weight_kg": 0.1,  "unit_value_usd": 25.00},
    {"category": "electronics", "description": "LED Driver Modules 12V 5A",                  "hs_code": "853590", "unit": "pieces",  "unit_weight_kg": 0.2,  "unit_value_usd": 18.00},
    {"category": "handicrafts", "description": "Hand Embroidered Silk Cushion Covers",       "hs_code": "630492", "unit": "pieces",  "unit_weight_kg": 0.4,  "unit_value_usd": 15.00},
    {"category": "handicrafts", "description": "Brass Decorative Figurines",                 "hs_code": "830629", "unit": "pieces",  "unit_weight_kg": 1.2,  "unit_value_usd": 22.00},
    {"category": "food",        "description": "Basmati Rice Long Grain Premium",            "hs_code": "100630", "unit": "bags",    "unit_weight_kg": 25.0, "unit_value_usd": 35.00},
    {"category": "food",        "description": "Organic Turmeric Powder",                    "hs_code": "091030", "unit": "bags",    "unit_weight_kg": 1.0,  "unit_value_usd": 4.50},
    {"category": "chemicals",   "description": "Industrial Solvent IPA 99% Pure",            "hs_code": "290512", "unit": "drums",   "unit_weight_kg": 0.9,  "unit_value_usd": 3.20},
    {"category": "auto",        "description": "Automotive Brake Pads Set",                  "hs_code": "870830", "unit": "sets",    "unit_weight_kg": 2.5,  "unit_value_usd": 28.00},
    {"category": "auto",        "description": "Two Wheeler Engine Parts",                   "hs_code": "840991", "unit": "pieces",  "unit_weight_kg": 3.5,  "unit_value_usd": 55.00},
]

TEMPLATES = ["modern", "classic", "minimal", "government"]

PORTS_OF_LOADING = [
    "Nhava Sheva (JNPT), Mumbai", "Chennai Sea Port", "Mundra Port, Gujarat",
    "Kolkata Sea Port", "Cochin Sea Port", "Visakhapatnam Port", "Kandla Port, Gujarat",
]

PAYMENT_TERMS = ["LC at Sight", "TT 30 days", "DA 60 days", "DP at Sight", "Open Account"]
PACKAGE_UNITS = ["CTNS", "PKGS", "BOXES", "CARTONS", "PALLETS"]
GROSS_LABELS  = ["Total Gross Weight:", "Gross Weight Total:", "Total Weight (Gross):"]
VALUE_LABELS  = ["Total FOB Value:", "Invoice Total (FOB):", "Total Value FOB USD:"]


def _random_date():
    d, m = random.randint(1, 28), random.randint(1, 12)
    fmts = [f"{d:02d}/{m:02d}/2024", f"{d:02d}-{m:02d}-2024",
            f"{d:02d}.{m:02d}.2024", f"2024/{m:02d}/{d:02d}"]
    return random.choice(fmts)


# ── Template header renderers ──────────────────────────────────────
def _hdr_modern(pdf, title):
    pdf.set_fill_color(25, 55, 109)
    pdf.rect(0, 0, 210, 25, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(10, 7)
    pdf.cell(0, 10, title)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(10, 30)


def _hdr_classic(pdf, title):
    pdf.rect(5, 5, 200, 287)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(10, 10)
    pdf.cell(0, 10, title, align="C")
    pdf.line(5, 22, 205, 22)
    pdf.set_xy(10, 28)


def _hdr_minimal(pdf, title):
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(10, 10)
    pdf.cell(0, 8, title)
    pdf.line(10, 20, 200, 20)
    pdf.set_xy(10, 25)


def _hdr_government(pdf, title):
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(10, 10)
    pdf.cell(0, 8, f"FORM - {title}", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(10, 19)
    pdf.cell(0, 6, "(As per Customs Act 1962)", align="C")
    pdf.rect(5, 5, 200, 25)
    pdf.set_xy(10, 35)


HDR = {
    "modern":     _hdr_modern,
    "classic":    _hdr_classic,
    "minimal":    _hdr_minimal,
    "government": _hdr_government,
}


def _render_parties(pdf, exp, imp):
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 5, "Exporter / Shipper:", ln=False)
    pdf.cell(0, 5, "Consignee / Importer:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(95, 5, exp["name"], ln=False)
    pdf.cell(0, 5, imp["name"], ln=True)
    pdf.cell(95, 5, f"{exp['city']}, {exp['state']}, India", ln=False)
    pdf.cell(0, 5, f"{imp['city']}, {imp['country']}", ln=True)
    pdf.cell(95, 5, f"IEC: {exp['iec']}", ln=False)
    pdf.cell(0, 5, f"Country: {imp['country']}", ln=True)
    pdf.ln(4)


def create_invoice_pdf(data, output_path):
    pdf = FPDF()
    pdf.add_page()
    HDR[data["template"]](pdf, "COMMERCIAL INVOICE")

    pdf.set_font("Helvetica", "", 9)
    inv_no = f"INV/{data['doc_id']:04d}/2024"
    pdf.cell(0, 5, f"Invoice No: {inv_no}", ln=True)
    pdf.cell(0, 5, f"Date: {data['date']}", ln=True)
    pdf.cell(0, 5, f"Port of Loading: {data['port_loading']}", ln=True)
    pdf.cell(0, 5, f"Port of Discharge: {data['port_discharge']}", ln=True)
    pdf.ln(3)

    _render_parties(pdf, data["exporter"], data["importer"])

    # table header
    col_w = [65, 18, 22, 28, 25, 25]
    hdrs  = ["Description of Goods", "Qty", "Unit", "HS Code", "Gross Wt", "FOB Value"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 220, 220)
    for h, w in zip(hdrs, col_w):
        pdf.cell(w, 6, h, border=1, fill=True)
    pdf.ln()

    inv, prod = data["invoice"], data["product"]
    n_lines = random.randint(1, 3)
    rem_w, rem_v = inv["total_weight_kg"], inv["total_value_usd"]

    pdf.set_font("Helvetica", "", 8)
    for li in range(n_lines):
        if li == n_lines - 1:
            lw, lv = rem_w, rem_v
        else:
            lw = round(rem_w * random.uniform(0.3, 0.6), 2)
            lv = round(rem_v * random.uniform(0.3, 0.6), 2)
            rem_w = round(rem_w - lw, 2)
            rem_v = round(rem_v - lv, 2)
        row = [prod["description"][:30], str(data["quantity"] // n_lines),
               prod["unit"], inv["hs_code"], f"{lw} KG", f"USD {lv:.2f}"]
        for val, w in zip(row, col_w):
            pdf.cell(w, 6, str(val), border=1)
        pdf.ln()

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, f"{random.choice(GROSS_LABELS)} {inv['total_weight_kg']} KGS", ln=True)
    pdf.cell(0, 5, f"{random.choice(VALUE_LABELS)} USD {inv['total_value_usd']:.2f}", ln=True)
    pdf.cell(0, 5, "Country of Origin: India", ln=True)
    pdf.cell(0, 5, f"Terms of Payment: {random.choice(PAYMENT_TERMS)}", ln=True)

    pdf.output(output_path)


def create_packing_list_pdf(data, output_path):
    pdf = FPDF()
    pdf.add_page()
    HDR[data["template"]](pdf, "PACKING LIST")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Packing List No: PL/{data['doc_id']:04d}/2024", ln=True)
    pdf.cell(0, 5, f"Ref Invoice No: INV/{data['doc_id']:04d}/2024", ln=True)
    pdf.cell(0, 5, f"Date: {data['date']}", ln=True)
    pdf.ln(3)

    _render_parties(pdf, data["exporter"], data["importer"])

    col_w = [50, 18, 22, 25, 30, 30, 15]
    hdrs  = ["Description", "Qty", "HS Code", "Packages", "Net Wt", "Gross Wt", "CBM"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 220, 220)
    for h, w in zip(hdrs, col_w):
        pdf.cell(w, 6, h, border=1, fill=True)
    pdf.ln()

    pl, prod = data["packing_list"], data["product"]
    packages  = max(1, data["quantity"] // random.randint(8, 12))
    net_wt    = round(pl["total_weight_kg"] * 0.92, 2)
    cbm       = round(random.uniform(0.5, 5.0), 3)

    pdf.set_font("Helvetica", "", 8)
    row = [prod["description"][:25], str(data["quantity"]), pl["hs_code"],
           str(packages), f"{net_wt} KG", f"{pl['total_weight_kg']} KG", str(cbm)]
    for val, w in zip(row, col_w):
        pdf.cell(w, 6, str(val), border=1)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, f"{random.choice(GROSS_LABELS)} {pl['total_weight_kg']} KGS", ln=True)
    pdf.cell(0, 5, f"Total Net Weight: {net_wt} KGS", ln=True)
    pdf.cell(0, 5, f"Total Packages: {packages} {random.choice(PACKAGE_UNITS)}", ln=True)
    pdf.cell(0, 5, f"Total CBM: {cbm}", ln=True)

    pdf.output(output_path)


def add_scan_noise(pdf_path, noise_level):
    """Convert PDF to PNG and add realistic scan noise."""
    try:
        import fitz
        from PIL import Image, ImageFilter, ImageEnhance
        import numpy as np

        doc = fitz.open(pdf_path)
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        if noise_level == "light":
            img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
            img = ImageEnhance.Brightness(img).enhance(random.uniform(0.93, 1.05))

        elif noise_level == "medium":
            img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
            arr = np.clip(np.array(img, np.float32) + np.random.normal(0, 8, np.array(img).shape), 0, 255).astype(np.uint8)
            img = Image.fromarray(arr).rotate(random.uniform(-0.8, 0.8), fillcolor=(255, 255, 255))

        elif noise_level == "heavy":
            img = img.filter(ImageFilter.GaussianBlur(radius=1.0))
            arr = np.clip(np.array(img, np.float32) + np.random.normal(0, 15, np.array(img).shape), 0, 255).astype(np.uint8)
            img = Image.fromarray(arr).rotate(random.uniform(-1.5, 1.5), fillcolor=(255, 255, 255))
            img = ImageEnhance.Contrast(img).enhance(random.uniform(0.85, 1.1))

        png_path = pdf_path.replace(".pdf", ".png")
        img.save(png_path)

    except Exception as e:
        print(f"  [noise] {e}")


def generate_document_pair(doc_id, inject_errors=False):
    exporter = random.choice(EXPORTERS)
    importer = random.choice(IMPORTERS)
    product  = random.choice(PRODUCTS)
    quantity = random.randint(50, 2000)
    template = random.choice(TEMPLATES)
    noise    = random.choices(["none", "light", "medium", "heavy"], weights=[40, 30, 20, 10])[0]

    total_weight = round(quantity * product["unit_weight_kg"], 2)
    total_value  = round(quantity * random.uniform(0.88, 1.12) * product["unit_value_usd"], 2)
    hs_code      = product["hs_code"]

    pl_weight, pl_hs_code = total_weight, hs_code
    errors_injected = []

    if inject_errors:
        error_types = random.sample(["weight", "hs_code"], k=random.randint(1, 2))
        if "weight" in error_types:
            pl_weight = round(total_weight * random.uniform(1.04, 1.30), 2)
            errors_injected.append({"type": "WEIGHT_MISMATCH", "invoice_weight": total_weight, "packing_weight": pl_weight})
        if "hs_code" in error_types:
            pl_hs_code = hs_code[:-2] + str(random.randint(10, 99)).zfill(2)
            errors_injected.append({"type": "HS_CODE_MISMATCH", "invoice_hs": hs_code, "packing_hs": pl_hs_code})

    return {
        "doc_id": doc_id, "template": template, "noise_level": noise,
        "date": _random_date(), "port_loading": random.choice(PORTS_OF_LOADING),
        "port_discharge": f"{importer['city']} Port",
        "exporter": exporter, "importer": importer, "product": product,
        "quantity": quantity,
        "invoice":      {"total_weight_kg": total_weight, "total_value_usd": total_value, "hs_code": hs_code},
        "packing_list": {"total_weight_kg": pl_weight, "hs_code": pl_hs_code},
        "has_errors": inject_errors, "errors_injected": errors_injected,
        "expected_status": "REJECTED" if errors_injected else "PASSED",
    }


def generate_dataset(num_pairs=2000, output_dir="data/training_v2"):
    os.makedirs(f"{output_dir}/invoices", exist_ok=True)
    os.makedirs(f"{output_dir}/packing_lists", exist_ok=True)
    random.seed(42)

    labels = []
    stats  = {"templates": {}, "noise": {}, "categories": {}, "clean": 0, "errors": 0}

    for i in range(num_pairs):
        inject_errors = i % 2 == 1
        doc = generate_document_pair(i + 1, inject_errors)

        inv_path = f"{output_dir}/invoices/invoice_{i+1:04d}.pdf"
        pl_path  = f"{output_dir}/packing_lists/pl_{i+1:04d}.pdf"

        create_invoice_pdf(doc, inv_path)
        create_packing_list_pdf(doc, pl_path)

        if doc["noise_level"] != "none":
            add_scan_noise(inv_path, doc["noise_level"])
            add_scan_noise(pl_path,  doc["noise_level"])

        stats["templates"][doc["template"]] = stats["templates"].get(doc["template"], 0) + 1
        stats["noise"][doc["noise_level"]]  = stats["noise"].get(doc["noise_level"], 0) + 1
        stats["categories"][doc["product"]["category"]] = stats["categories"].get(doc["product"]["category"], 0) + 1
        if inject_errors: stats["errors"] += 1
        else:             stats["clean"]  += 1

        labels.append({
            "id": i + 1, "invoice_path": inv_path, "packing_list_path": pl_path,
            "template": doc["template"], "noise_level": doc["noise_level"],
            "expected_status": doc["expected_status"], "errors": doc["errors_injected"],
            "product_category": doc["product"]["category"],
        })

        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{num_pairs} | clean={stats['clean']} errors={stats['errors']}")

    with open(f"{output_dir}/labels.json", "w") as f:
        json.dump(labels, f, indent=2)

    print(f"\n=== Dataset v2 stats ===")
    print(f"  Total : {num_pairs}  (clean={stats['clean']}, errors={stats['errors']})")
    print(f"  Templates  : {stats['templates']}")
    print(f"  Noise      : {stats['noise']}")
    print(f"  Categories : {stats['categories']}")
    print(f"  Labels     : {output_dir}/labels.json")
    return labels


if __name__ == "__main__":
    print("Generating 2000 diverse document pairs...")
    generate_dataset(2000)
