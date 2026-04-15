"""
TradeVision — Phase 4 Demo UI
Streamlit front-end for the AI-powered trade compliance checker.

Run:
    source venv/bin/activate
    streamlit run app.py --server.port 8501
"""

import streamlit as st
import requests
import json
import time
import fitz
import io
from PIL import Image

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="TradeVision — AI Compliance Checker",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import os

# Priority: Streamlit secrets → env var → localhost fallback
try:
    API_URL = st.secrets["TRADEVISION_API_URL"].rstrip("/")
except Exception:
    API_URL = os.getenv("TRADEVISION_API_URL", "http://localhost:8000").rstrip("/")

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* Dark background */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1320 50%, #0a0e1a 100%);
    color: #e2e8f0;
}

/* Hero header */
.hero-header {
    text-align: center;
    padding: 2.5rem 0 1.5rem 0;
}
.hero-title {
    font-size: 3rem;
    font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
}
.hero-sub {
    color: #94a3b8;
    font-size: 1.1rem;
    font-weight: 400;
}

/* Upload zone */
.stFileUploader {
    background: rgba(255,255,255,0.03) !important;
    border: 2px dashed rgba(96, 165, 250, 0.3) !important;
    border-radius: 16px !important;
    padding: 1rem !important;
    transition: border-color 0.3s ease;
}
.stFileUploader:hover {
    border-color: rgba(96, 165, 250, 0.7) !important;
}

/* Verdict banners */
.verdict-pass {
    background: linear-gradient(135deg, #064e3b, #065f46);
    border: 2px solid #34d399;
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
    margin: 1.5rem 0;
    box-shadow: 0 0 40px rgba(52, 211, 153, 0.2);
    animation: pulse-green 2s infinite;
}
.verdict-reject {
    background: linear-gradient(135deg, #450a0a, #7f1d1d);
    border: 2px solid #f87171;
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
    margin: 1.5rem 0;
    box-shadow: 0 0 40px rgba(248, 113, 113, 0.25);
    animation: pulse-red 1.5s infinite;
}
.verdict-review {
    background: linear-gradient(135deg, #451a03, #7c2d12);
    border: 2px solid #fb923c;
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
    margin: 1.5rem 0;
    box-shadow: 0 0 40px rgba(251, 146, 60, 0.2);
}
@keyframes pulse-green {
    0%, 100% { box-shadow: 0 0 40px rgba(52, 211, 153, 0.2); }
    50%       { box-shadow: 0 0 60px rgba(52, 211, 153, 0.45); }
}
@keyframes pulse-red {
    0%, 100% { box-shadow: 0 0 40px rgba(248, 113, 113, 0.25); }
    50%       { box-shadow: 0 0 70px rgba(248, 113, 113, 0.55); }
}
.verdict-icon  { font-size: 3.5rem; }
.verdict-text  { font-size: 2rem; font-weight: 800; margin-top: 0.5rem; letter-spacing: 0.05em; }
.verdict-sub   { font-size: 1rem; opacity: 0.8; margin-top: 0.25rem; }

/* Metric cards */
.metric-row {
    display: flex;
    gap: 1rem;
    margin: 1rem 0;
    flex-wrap: wrap;
}
.metric-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1rem 1.5rem;
    flex: 1;
    min-width: 120px;
    text-align: center;
}
.metric-val { font-size: 1.8rem; font-weight: 700; }
.metric-lbl { font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem; text-transform: uppercase; letter-spacing: 0.08em; }

/* Flag cards */
.flag-critical {
    background: rgba(127, 29, 29, 0.4);
    border-left: 4px solid #f87171;
    border-radius: 0 10px 10px 0;
    padding: 0.85rem 1rem;
    margin: 0.5rem 0;
}
.flag-high {
    background: rgba(120, 53, 15, 0.4);
    border-left: 4px solid #fb923c;
    border-radius: 0 10px 10px 0;
    padding: 0.85rem 1rem;
    margin: 0.5rem 0;
}
.flag-medium {
    background: rgba(66, 32, 6, 0.4);
    border-left: 4px solid #fbbf24;
    border-radius: 0 10px 10px 0;
    padding: 0.85rem 1rem;
    margin: 0.5rem 0;
}
.flag-low {
    background: rgba(30, 58, 138, 0.3);
    border-left: 4px solid #60a5fa;
    border-radius: 0 10px 10px 0;
    padding: 0.85rem 1rem;
    margin: 0.5rem 0;
}
.flag-id   { font-size: 0.7rem; font-family: monospace; color: #94a3b8; }
.flag-title { font-weight: 600; font-size: 0.9rem; }
.flag-sum  { font-size: 0.8rem; color: #cbd5e1; margin-top: 0.25rem; }

/* Issue cards */
.issue-card {
    background: rgba(127, 29, 29, 0.3);
    border: 1px solid rgba(248, 113, 113, 0.3);
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin: 0.5rem 0;
}

/* Section headers */
.section-header {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #60a5fa;
    margin: 1.5rem 0 0.75rem 0;
    border-bottom: 1px solid rgba(96, 165, 250, 0.2);
    padding-bottom: 0.4rem;
}

/* Field pill */
.field-pill {
    display: inline-block;
    background: rgba(167, 139, 250, 0.15);
    border: 1px solid rgba(167, 139, 250, 0.3);
    border-radius: 20px;
    padding: 0.2rem 0.75rem;
    font-size: 0.8rem;
    margin: 0.2rem;
    color: #c4b5fd;
}

/* Scan animation overlay */
.scan-bar {
    height: 3px;
    background: linear-gradient(90deg, transparent, #60a5fa, transparent);
    animation: scan 1.5s linear infinite;
}
@keyframes scan {
    0%   { transform: translateY(0); opacity: 1; }
    100% { transform: translateY(300px); opacity: 0; }
}

/* Divider */
.divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin: 1.5rem 0;
}

/* Document frame */
.doc-frame {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 0.75rem;
    text-align: center;
}
.doc-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 0.5rem;
}

button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 1.1rem !important;
    padding: 0.75rem 2rem !important;
    width: 100% !important;
    color: white !important;
    transition: opacity 0.2s !important;
}
button[data-testid="stBaseButton-primary"]:hover {
    opacity: 0.85 !important;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────

def pdf_to_image(uploaded_file, scale: float = 1.8) -> Image.Image:
    """Convert first page of uploaded PDF to PIL Image."""
    bytes_data = uploaded_file.read()
    uploaded_file.seek(0)
    doc = fitz.open(stream=bytes_data, filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def call_api(invoice_file, packing_file, endpoint="/check_v3"):
    """POST both PDFs to the TradeVision API."""
    invoice_file.seek(0)
    packing_file.seek(0)
    resp = requests.post(
        f"{API_URL}{endpoint}",
        files={
            "invoice":      (invoice_file.name, invoice_file, "application/pdf"),
            "packing_list": (packing_file.name, packing_file, "application/pdf"),
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def flag_html(flag: dict) -> str:
    sev   = flag.get("severity", "LOW")
    cls   = f"flag-{sev.lower()}"
    sev_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "📋", "LOW": "ℹ️"}.get(sev, "")
    return f"""
    <div class="{cls}">
        <div class="flag-id">{flag['rule_id']} &nbsp;·&nbsp; {flag['citation']}</div>
        <div class="flag-title">{sev_emoji} {flag['title']}</div>
        <div class="flag-sum">{flag.get('summary','')[:200]}</div>
    </div>
    """


def issue_html(issue: dict) -> str:
    t = issue.get("type", "UNKNOWN").replace("_", " ")
    d = issue.get("detail", issue.get("description", ""))
    return f"""
    <div class="issue-card">
        <strong>⛔ {t}</strong><br>
        <span style="color:#fca5a5;font-size:0.85rem">{d}</span>
    </div>
    """


def severity_color(sev: str) -> str:
    return {"CRITICAL": "#f87171", "HIGH": "#fb923c", "MEDIUM": "#fbbf24", "LOW": "#60a5fa"}.get(sev, "#94a3b8")


# ── UI Layout ───────────────────────────────────────────────────────

# Hero
st.markdown("""
<div class="hero-header">
    <div class="hero-title">🛡️ TradeVision</div>
    <div class="hero-sub">AI-Powered Trade Document Compliance · Indian Export Regulations</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# Upload row
col_inv, col_pl = st.columns(2)
with col_inv:
    st.markdown('<div class="section-header">📄 Commercial Invoice</div>', unsafe_allow_html=True)
    invoice_file = st.file_uploader("Drop Invoice PDF here", type=["pdf"], key="invoice", label_visibility="collapsed")

with col_pl:
    st.markdown('<div class="section-header">📦 Packing List</div>', unsafe_allow_html=True)
    packing_file = st.file_uploader("Drop Packing List PDF here", type=["pdf"], key="packing", label_visibility="collapsed")

st.markdown('<br>', unsafe_allow_html=True)

# Show previews if both uploaded
if invoice_file and packing_file:
    prev_col1, prev_col2 = st.columns(2)
    with prev_col1:
        try:
            inv_img = pdf_to_image(invoice_file)
            st.markdown('<div class="doc-frame"><div class="doc-label">Invoice Preview</div>', unsafe_allow_html=True)
            st.image(inv_img, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Preview error: {e}")

    with prev_col2:
        try:
            pl_img = pdf_to_image(packing_file)
            st.markdown('<div class="doc-frame"><div class="doc-label">Packing List Preview</div>', unsafe_allow_html=True)
            st.image(pl_img, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Preview error: {e}")

    st.markdown('<br>', unsafe_allow_html=True)

    # Analyze button
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        analyse = st.button("🔍  Run Compliance Check", type="primary", use_container_width=True)

    if analyse:
        # Scanning animation
        progress_area = st.empty()
        with progress_area.container():
            st.markdown("""
            <div style='text-align:center; padding: 2rem;'>
                <div style='font-size:2rem; margin-bottom:1rem;'>⚡</div>
                <div style='font-size:1.1rem; color:#60a5fa; font-weight:600;'>Scanning Documents...</div>
                <div style='color:#64748b; font-size:0.85rem; margin-top:0.5rem;'>VLM visual extraction → Regex cross-check → RAG compliance lookup</div>
            </div>
            """, unsafe_allow_html=True)
            prog = st.progress(0)
            steps = [
                (15, "📸  Rendering document images..."),
                (35, "🤖  Vision model extracting fields..."),
                (55, "📏  Cross-checking weights & HS codes..."),
                (75, "📚  Querying 18 Indian customs regulations..."),
                (90, "⚖️  Computing final compliance verdict..."),
            ]
            status_txt = st.empty()
            for pct, msg in steps:
                status_txt.markdown(f"<div style='text-align:center;color:#94a3b8;font-size:0.85rem'>{msg}</div>", unsafe_allow_html=True)
                prog.progress(pct)
                time.sleep(0.4)

        # Actual API call
        try:
            result = call_api(invoice_file, packing_file, "/check_v3")
            prog.progress(100)
            time.sleep(0.2)
            progress_area.empty()
        except Exception as e:
            progress_area.empty()
            st.error(f"❌ API Error: {e}\n\nMake sure the TradeVision API is running on port 8000.")
            st.stop()

        # ── VERDICT BANNER ─────────────────────────────────────────
        status = result.get("status", "NEEDS_REVIEW")
        summary_block = result.get("summary", {})
        n_issues  = summary_block.get("vlm_issues_count", 0) + summary_block.get("phase1_issues_count", 0)
        n_flags   = summary_block.get("regulatory_flags_count", 0)
        n_crit    = summary_block.get("critical_flags", 0)

        if status == "PASSED":
            st.markdown(f"""
            <div class="verdict-pass">
                <div class="verdict-icon">✅</div>
                <div class="verdict-text" style="color:#34d399">PASSED — COMPLIANT</div>
                <div class="verdict-sub" style="color:#6ee7b7">
                    No discrepancies detected · {n_flags} regulatory rules reviewed
                </div>
            </div>""", unsafe_allow_html=True)

        elif status == "REJECTED":
            st.markdown(f"""
            <div class="verdict-reject">
                <div class="verdict-icon">🚨</div>
                <div class="verdict-text" style="color:#f87171">REJECTED — CRITICAL FLAGS</div>
                <div class="verdict-sub" style="color:#fca5a5">
                    {n_issues} document discrepanc{'y' if n_issues==1 else 'ies'} ·
                    {n_crit} critical regulatory violation{'s' if n_crit!=1 else ''}
                </div>
            </div>""", unsafe_allow_html=True)

        else:
            st.markdown(f"""
            <div class="verdict-review">
                <div class="verdict-icon">⚠️</div>
                <div class="verdict-text" style="color:#fb923c">NEEDS REVIEW</div>
                <div class="verdict-sub" style="color:#fed7aa">
                    {n_flags} regulatory considerations flagged — manual review recommended
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<hr class="divider">', unsafe_allow_html=True)

        # ── METRICS ROW ────────────────────────────────────────────
        phase1_issues = result.get("phase1_comparison", {}).get("issues", [])
        vlm_issues    = result.get("vlm_result", {}).get("issues", [])
        reg_flags     = result.get("regulatory_flags", [])
        fields        = result.get("document_fields", {})

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-val" style="color:#f87171">{len(phase1_issues)}</div>
                <div class="metric-lbl">Doc Issues</div></div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-val" style="color:#f87171">{n_crit}</div>
                <div class="metric-lbl">Critical Flags</div></div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-val" style="color:#fbbf24">{n_flags}</div>
                <div class="metric-lbl">Reg Rules Hit</div></div>""", unsafe_allow_html=True)
        with m4:
            hs = fields.get("hs_codes", [])
            st.markdown(f"""<div class="metric-card">
                <div class="metric-val" style="color:#a78bfa">{len(hs)}</div>
                <div class="metric-lbl">HS Codes</div></div>""", unsafe_allow_html=True)
        with m5:
            cat = fields.get("product_category", "—").capitalize()
            st.markdown(f"""<div class="metric-card">
                <div class="metric-val" style="color:#34d399;font-size:1.1rem">{cat}</div>
                <div class="metric-lbl">Category</div></div>""", unsafe_allow_html=True)

        st.markdown('<br>', unsafe_allow_html=True)

        # ── DETAIL COLUMNS ──────────────────────────────────────────
        left_col, right_col = st.columns([1, 1])

        with left_col:
            # Document discrepancies
            all_issues = phase1_issues + vlm_issues
            if all_issues:
                st.markdown('<div class="section-header">⛔ Document Discrepancies</div>', unsafe_allow_html=True)
                for issue in all_issues:
                    st.markdown(issue_html(issue), unsafe_allow_html=True)
            else:
                st.markdown('<div class="section-header">✅ Document Fields</div>', unsafe_allow_html=True)
                st.markdown("""<div style='background:rgba(6,78,59,0.3);border:1px solid rgba(52,211,153,0.3);
                    border-radius:10px;padding:0.85rem 1rem;color:#6ee7b7;'>
                    ✅ No weight or HS code discrepancies detected between invoice and packing list.
                </div>""", unsafe_allow_html=True)

            # Extracted fields
            st.markdown('<div class="section-header">🔬 Extracted Fields</div>', unsafe_allow_html=True)
            field_items = {
                "Document Type": fields.get("document_type", "—"),
                "Category":      fields.get("product_category", "—"),
                "Destination":   fields.get("importer_country", "—"),
                "IEC Present":   "✅ Yes" if fields.get("iec_present") else "❌ No",
                "SCOMET Required": "⚠️ Yes" if fields.get("requires_scomet") else "No",
                "RCMC Required": "Yes" if fields.get("requires_rcmc") else "No",
                "FSSAI Required": "Yes" if fields.get("requires_fssai") else "No",
            }
            if fields.get("invoice_value_usd"):
                field_items["Invoice Value"] = f"USD {fields['invoice_value_usd']:,.2f}"
            rows = ""
            for k, v in field_items.items():
                rows += f"<tr><td style='color:#94a3b8;padding:0.3rem 0.6rem;font-size:0.82rem'>{k}</td><td style='padding:0.3rem 0.6rem;font-size:0.82rem;font-weight:500'>{v}</td></tr>"
            st.markdown(f"""<table style='width:100%;border-collapse:collapse;
                background:rgba(255,255,255,0.03);border-radius:10px;overflow:hidden;'>
                {rows}</table>""", unsafe_allow_html=True)

            if hs:
                st.markdown('<div class="section-header">🏷️ HS Codes Detected</div>', unsafe_allow_html=True)
                pills = "".join(f'<span class="field-pill">{h}</span>' for h in hs)
                st.markdown(f"<div>{pills}</div>", unsafe_allow_html=True)

        with right_col:
            # Regulatory flags
            if reg_flags:
                st.markdown(f'<div class="section-header">📚 Regulatory Flags ({len(reg_flags)} rules)</div>', unsafe_allow_html=True)
                # Show critical/high first, then rest in expander
                priority = [f for f in reg_flags if f["severity"] in ("CRITICAL", "HIGH")]
                rest     = [f for f in reg_flags if f["severity"] not in ("CRITICAL", "HIGH")]

                for flag in priority:
                    st.markdown(flag_html(flag), unsafe_allow_html=True)

                if rest:
                    with st.expander(f"Show {len(rest)} lower-severity rules →"):
                        for flag in rest:
                            st.markdown(flag_html(flag), unsafe_allow_html=True)
            else:
                st.markdown('<div class="section-header">📚 Regulatory Status</div>', unsafe_allow_html=True)
                st.markdown("""<div style='background:rgba(6,78,59,0.3);border:1px solid rgba(52,211,153,0.3);
                    border-radius:10px;padding:0.85rem 1rem;color:#6ee7b7;'>
                    ✅ No specific regulatory concerns flagged by RAG checker.
                </div>""", unsafe_allow_html=True)

            # VLM summary
            vlm_summary = result.get("vlm_result", {}).get("summary", "")
            if vlm_summary:
                st.markdown('<div class="section-header">🤖 VLM Visual Analysis</div>', unsafe_allow_html=True)
                st.markdown(f"""<div style='background:rgba(30,58,138,0.3);border:1px solid rgba(96,165,250,0.2);
                    border-radius:10px;padding:0.85rem 1rem;color:#bfdbfe;font-size:0.85rem;
                    font-style:italic'>"{vlm_summary}"</div>""", unsafe_allow_html=True)

        # Raw JSON expander
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        with st.expander("🔧 Raw API Response (JSON)"):
            st.json(result)

else:
    # Empty state guidance
    st.markdown("""
    <div style='text-align:center; padding: 3rem; color: #475569;'>
        <div style='font-size: 3rem; margin-bottom: 1rem;'>📂</div>
        <div style='font-size: 1.1rem; font-weight: 600; color: #64748b;'>
            Upload an Invoice and Packing List PDF to begin
        </div>
        <div style='font-size: 0.9rem; margin-top: 0.5rem;'>
            The AI will visually scan both documents, detect discrepancies,<br>
            and cross-reference 18 Indian customs regulations in seconds.
        </div>
        <br>
        <div style='display:flex; justify-content:center; gap:2rem; flex-wrap:wrap; margin-top:1rem;'>
            <div style='background:rgba(96,165,250,0.08);border:1px solid rgba(96,165,250,0.2);
                border-radius:12px;padding:1rem 1.5rem;max-width:200px;'>
                <div style='font-size:1.5rem'>⚖️</div>
                <div style='font-size:0.8rem;color:#94a3b8;margin-top:0.5rem'>
                    Weight mismatch detection
                </div>
            </div>
            <div style='background:rgba(167,139,250,0.08);border:1px solid rgba(167,139,250,0.2);
                border-radius:12px;padding:1rem 1.5rem;max-width:200px;'>
                <div style='font-size:1.5rem'>🏷️</div>
                <div style='font-size:0.8rem;color:#94a3b8;margin-top:0.5rem'>
                    HS code cross-validation
                </div>
            </div>
            <div style='background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.2);
                border-radius:12px;padding:1rem 1.5rem;max-width:200px;'>
                <div style='font-size:1.5rem'>📚</div>
                <div style='font-size:0.8rem;color:#94a3b8;margin-top:0.5rem'>
                    RAG: 18 Indian customs rules
                </div>
            </div>
            <div style='background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.2);
                border-radius:12px;padding:1rem 1.5rem;max-width:200px;'>
                <div style='font-size:1.5rem'>🤖</div>
                <div style='font-size:0.8rem;color:#94a3b8;margin-top:0.5rem'>
                    Qwen2-VL visual scan
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Sidebar — about
with st.sidebar:
    st.markdown("### 🛡️ TradeVision v0.3")
    st.markdown("""
    **AI compliance check for Indian exporters.**

    **Pipeline:**
    1. 🤖 Qwen2-VL-7B visual scan
    2. 📏 Regex cross-validation
    3. 📚 RAG → 18 customs rules

    **Detects:**
    - Weight mismatches
    - HS code discrepancies
    - SCOMET / RCMC requirements
    - IEC violations
    - Customs Act penalties

    ---
    API: `localhost:8000`
    """)
    st.markdown("---")

    # Quick health check
    try:
        r = requests.get(f"{API_URL}/health", timeout=2)
        if r.status_code == 200:
            st.success("✅ API Connected")
        else:
            st.error("⚠️ API Error")
    except:
        st.error("❌ API Offline")
        st.caption("Start with: `uvicorn main:app --port 8000`")
