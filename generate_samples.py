"""
Day 2 — Generate realistic sample trade PDFs for testing.
Produces 2 sets: a MATCHING pair (should PASS) and a MISMATCHED pair (should REJECT).

Run: python3 generate_samples.py
Outputs go into: data/
"""

from fpdf import FPDF
import os

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def new_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


def header(pdf, title):
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(4)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)


def section(pdf, label, value):
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 7, label + ":", border=0)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, str(value), ln=True)


def table_row(pdf, cols, widths, bold=False):
    style = "B" if bold else ""
    pdf.set_font("Helvetica", style, 9)
    for text, w in zip(cols, widths):
        pdf.cell(w, 7, str(text), border=1)
    pdf.ln()


# ──────────────────────────────────────────────
# Set 1 — MATCHING (should PASS)
# ──────────────────────────────────────────────

def make_invoice_1():
    """Commercial Invoice — correct data"""
    pdf = new_pdf()
    header(pdf, "COMMERCIAL INVOICE")

    section(pdf, "Invoice No",       "INV-2024-00142")
    section(pdf, "Date",              "15 March 2024")
    section(pdf, "Exporter",          "Shree Fabrics Pvt Ltd, Surat, India")
    section(pdf, "Buyer",             "Al-Ansar Trading LLC, Dubai, UAE")
    section(pdf, "Port of Loading",   "Nhava Sheva (JNPT), Mumbai")
    section(pdf, "Port of Discharge", "Jebel Ali, Dubai")
    section(pdf, "Payment Terms",     "LC at Sight")
    section(pdf, "Currency",          "USD")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "Line Items:", ln=True)

    widths = [15, 65, 20, 22, 25, 25]
    table_row(pdf, ["S.No", "Description", "HS Code", "Qty (pcs)", "Unit Price", "Total (USD)"], widths, bold=True)
    table_row(pdf, ["1", "Men's Cotton Shirts (Plain)", "620520", "500", "12.00", "6000.00"], widths)
    table_row(pdf, ["2", "Men's Denim Trousers",        "620342", "300", "18.50", "5550.00"], widths)
    table_row(pdf, ["3", "Women's Kurta Set (Cotton)",  "620441", "200", "15.00", "3000.00"], widths)

    pdf.ln(3)
    section(pdf, "Total Quantity",     "1000 pcs")
    section(pdf, "Gross Weight",       "320 kg")
    section(pdf, "Net Weight",         "305 kg")
    section(pdf, "No. of Cartons",     "40")
    section(pdf, "Total Invoice Value","USD 14,550.00")
    section(pdf, "IEC Code",           "0815099123")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 6, "Declaration: We declare that this invoice shows the actual price of the goods described and "
                          "that all particulars are true and correct. Goods are of Indian Origin.")

    pdf.output(f"{OUTPUT_DIR}/invoice_1_correct.pdf")
    print(f"  Created: {OUTPUT_DIR}/invoice_1_correct.pdf")


def make_packing_list_1():
    """Packing List — matches Invoice 1 exactly"""
    pdf = new_pdf()
    header(pdf, "PACKING LIST")

    section(pdf, "Packing List No",  "PL-2024-00142")
    section(pdf, "Invoice Ref",       "INV-2024-00142")
    section(pdf, "Date",              "15 March 2024")
    section(pdf, "Exporter",          "Shree Fabrics Pvt Ltd, Surat, India")
    section(pdf, "Buyer",             "Al-Ansar Trading LLC, Dubai, UAE")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "Packing Details:", ln=True)

    widths = [10, 55, 20, 18, 20, 22, 22]
    table_row(pdf, ["Box", "Description", "HS Code", "Qty (pcs)", "Cartons", "Net Wt (kg)", "Gross Wt (kg)"], widths, bold=True)
    table_row(pdf, ["1",  "Men's Cotton Shirts (Plain)", "620520", "500", "20", "120", "126"], widths)
    table_row(pdf, ["2",  "Men's Denim Trousers",        "620342", "300", "12", "105", "111"], widths)
    table_row(pdf, ["3",  "Women's Kurta Set (Cotton)",  "620441", "200", "8",  "80",  "83"], widths)

    pdf.ln(3)
    section(pdf, "Total Quantity",  "1000 pcs")
    section(pdf, "Total Cartons",   "40")
    section(pdf, "Net Weight",      "305 kg")
    section(pdf, "Gross Weight",    "320 kg")

    pdf.output(f"{OUTPUT_DIR}/packing_list_1_correct.pdf")
    print(f"  Created: {OUTPUT_DIR}/packing_list_1_correct.pdf")


# ──────────────────────────────────────────────
# Set 2 — MISMATCHED (should REJECT)
# ──────────────────────────────────────────────

def make_invoice_2():
    """Commercial Invoice — with deliberate errors for testing"""
    pdf = new_pdf()
    header(pdf, "COMMERCIAL INVOICE")

    section(pdf, "Invoice No",       "INV-2024-00199")
    section(pdf, "Date",              "20 March 2024")
    section(pdf, "Exporter",          "Krishna Pharma Exports, Hyderabad, India")
    section(pdf, "Buyer",             "MedSupply GmbH, Frankfurt, Germany")
    section(pdf, "Port of Loading",   "Chennai Sea Port")
    section(pdf, "Port of Discharge", "Hamburg, Germany")
    section(pdf, "Payment Terms",     "TT 30 Days")
    section(pdf, "Currency",          "USD")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "Line Items:", ln=True)

    widths = [15, 65, 20, 22, 25, 25]
    table_row(pdf, ["S.No", "Description", "HS Code", "Qty (units)", "Unit Price", "Total (USD)"], widths, bold=True)
    # HS Code on invoice: 300490 (generic pharma)
    table_row(pdf, ["1", "Paracetamol 500mg Tablets (10x10 blister)", "300490", "5000", "2.50", "12500.00"], widths)
    table_row(pdf, ["2", "Ibuprofen 400mg Tablets (10x10 blister)",   "300490", "3000", "3.00", "9000.00"], widths)

    pdf.ln(3)
    section(pdf, "Total Quantity", "8000 units")
    # DELIBERATE ERROR: Invoice says 180 kg, packing list will say 215 kg
    section(pdf, "Gross Weight",   "180 kg")
    section(pdf, "Net Weight",     "165 kg")
    section(pdf, "No. of Cartons", "50")
    section(pdf, "Total Value",    "USD 21,500.00")

    pdf.output(f"{OUTPUT_DIR}/invoice_2_errors.pdf")
    print(f"  Created: {OUTPUT_DIR}/invoice_2_errors.pdf  ← has deliberate errors")


def make_packing_list_2():
    """Packing List — mismatches Invoice 2 (weight + HS code both wrong)"""
    pdf = new_pdf()
    header(pdf, "PACKING LIST")

    section(pdf, "Packing List No", "PL-2024-00199")
    section(pdf, "Invoice Ref",      "INV-2024-00199")
    section(pdf, "Date",             "20 March 2024")
    section(pdf, "Exporter",         "Krishna Pharma Exports, Hyderabad, India")
    section(pdf, "Buyer",            "MedSupply GmbH, Frankfurt, Germany")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "Packing Details:", ln=True)

    widths = [10, 55, 20, 18, 20, 22, 22]
    table_row(pdf, ["Box", "Description", "HS Code", "Qty", "Cartons", "Net Wt (kg)", "Gross Wt (kg)"], widths, bold=True)
    # DELIBERATE ERROR: HS code 300410 here vs 300490 in invoice
    table_row(pdf, ["1", "Paracetamol 500mg Tablets", "300410", "5000", "25", "100", "108"], widths)
    table_row(pdf, ["2", "Ibuprofen 400mg Tablets",   "300410", "3000", "25", "100", "107"], widths)

    pdf.ln(3)
    section(pdf, "Total Quantity", "8000 units")
    section(pdf, "Total Cartons",  "50")
    # DELIBERATE ERROR: weight 215 kg vs 180 kg in invoice
    section(pdf, "Net Weight",     "200 kg")
    section(pdf, "Gross Weight",   "215 kg")

    pdf.output(f"{OUTPUT_DIR}/packing_list_2_errors.pdf")
    print(f"  Created: {OUTPUT_DIR}/packing_list_2_errors.pdf  ← has deliberate errors")


# ──────────────────────────────────────────────
# Bill of Lading (bonus)
# ──────────────────────────────────────────────

def make_bill_of_lading():
    pdf = new_pdf()
    header(pdf, "BILL OF LADING")

    section(pdf, "B/L No",              "MSCUIN240815")
    section(pdf, "Shipper",             "Shree Fabrics Pvt Ltd, Surat, India")
    section(pdf, "Consignee",           "Al-Ansar Trading LLC, Dubai, UAE")
    section(pdf, "Notify Party",        "Same as Consignee")
    section(pdf, "Vessel / Voyage",     "MSC ANIBAL / 024E")
    section(pdf, "Port of Loading",     "Nhava Sheva (JNPT), Mumbai, India")
    section(pdf, "Port of Discharge",   "Jebel Ali, Dubai, UAE")
    section(pdf, "Place of Delivery",   "Dubai, UAE")
    section(pdf, "Date of Issue",       "18 March 2024")
    section(pdf, "Freight",             "PREPAID")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "Particulars Furnished by Shipper:", ln=True)

    widths = [30, 70, 40, 30]
    table_row(pdf, ["Container No", "Description of Goods", "Gross Weight", "Measurement"], widths, bold=True)
    table_row(pdf, ["MSCU1234567", "Readymade Garments (Cotton) - 40 Ctns", "320 KGS", "2.5 CBM"], widths)

    pdf.ln(3)
    section(pdf, "No. of Containers", "1 x 20' FCL")
    section(pdf, "Total Packages",    "40 Cartons")
    section(pdf, "HS Code",           "620520 / 620342 / 620441")
    section(pdf, "Shipping Bill No",  "SB/2024/08/12345")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 6, "Shipped on Board. This Bill of Lading is issued subject to the terms and conditions "
                          "of the carrier's standard Bill of Lading. One original Bill of Lading duly endorsed "
                          "must be surrendered in exchange for the goods.")

    pdf.output(f"{OUTPUT_DIR}/bill_of_lading_1.pdf")
    print(f"  Created: {OUTPUT_DIR}/bill_of_lading_1.pdf")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating sample trade documents...\n")
    print("Set 1 — Correct documents (should PASS compliance):")
    make_invoice_1()
    make_packing_list_1()

    print("\nSet 2 — Documents with errors (should REJECT):")
    make_invoice_2()
    make_packing_list_2()

    print("\nBonus:")
    make_bill_of_lading()

    print("\n✅ All sample documents created in ./data/")
    print("\nExpected compliance results:")
    print("  invoice_1_correct + packing_list_1_correct  →  PASSED")
    print("  invoice_2_errors  + packing_list_2_errors   →  REJECTED (weight + HS code mismatch)")
