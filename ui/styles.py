"""
ui/styles.py
------------
Dark-theme CSS injection and shared style helpers.
Import inject_css() at the top of every page.
"""

import streamlit as st


# ---------------------------------------------------------------------------
# Design System Tokens
# ---------------------------------------------------------------------------

THEME = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "surface2": "#1c2128",
    "border": "#30363d",
    "primary": "#00d4aa",         # Buy / positive
    "danger": "#ff4d6d",          # Stop / negative
    "warning": "#f5a623",         # Warning / neutral
    "accent": "#388bfd",          # Links / info
    "text": "#e6edf3",
    "text_secondary": "#8b949e",
    "font": "'Inter', system-ui, -apple-system, sans-serif",
}


# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Root & body ──────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"], .main .block-container {
    background-color: #0d1117 !important;
    color: #e6edf3 !important;
    font-family: 'Inter', system-ui, sans-serif !important;
}

[data-testid="stSidebar"] {
    background-color: #161b22 !important;
    border-right: 1px solid #30363d !important;
}

/* ── Headings ──────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
    color: #e6edf3 !important;
    font-family: 'Inter', system-ui, sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
}

h1 { font-size: 1.8rem !important; }
h2 { font-size: 1.4rem !important; }
h3 { font-size: 1.15rem !important; }

/* ── Metric cards ─────────────────────────────── */
[data-testid="metric-container"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
    padding: 14px 18px !important;
    transition: border-color 0.2s;
}
[data-testid="metric-container"]:hover {
    border-color: #388bfd !important;
}
[data-testid="stMetricLabel"] {
    color: #8b949e !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="stMetricValue"] {
    color: #e6edf3 !important;
    font-size: 1.35rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricDelta"] svg { display: none; }

/* ── Buttons ──────────────────────────────────── */
.stButton > button {
    background: #161b22 !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    transition: all 0.18s ease !important;
}
.stButton > button:hover {
    border-color: #00d4aa !important;
    color: #00d4aa !important;
    box-shadow: 0 0 0 2px rgba(0,212,170,0.15) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00d4aa, #00b894) !important;
    border: none !important;
    color: #0d1117 !important;
    font-weight: 700 !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 20px rgba(0,212,170,0.4) !important;
    transform: translateY(-1px) !important;
}

/* ── Inputs ───────────────────────────────────── */
.stNumberInput > div > div > input,
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
    font-family: 'Inter', sans-serif !important;
}
.stNumberInput > div > div > input:focus,
.stTextInput > div > div > input:focus {
    border-color: #388bfd !important;
    box-shadow: 0 0 0 3px rgba(56,139,253,0.15) !important;
}

/* ── Sliders ──────────────────────────────────── */
[data-testid="stSlider"] > div > div > div > div {
    background: #00d4aa !important;
}

/* ── Tabs ─────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #161b22 !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid #30363d !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #8b949e !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.18s !important;
}
.stTabs [aria-selected="true"] {
    background: #0d1117 !important;
    color: #e6edf3 !important;
    font-weight: 600 !important;
}

/* ── DataFrames / tables ──────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
}


/* ── Expanders ────────────────────────────────── */
[data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"]:hover {
    border-color: #30363d !important;
}

/* ── Containers / cards ───────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
}

/* ── Divider ──────────────────────────────────── */
hr { border-color: #30363d !important; }

/* ── Sidebar nav links ────────────────────────── */
[data-testid="stSidebarNav"] a {
    color: #8b949e !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}
[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: rgba(0,212,170,0.1) !important;
    color: #00d4aa !important;
}

/* ── Pills ────────────────────────────────────── */
[data-testid="stPills"] button {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #8b949e !important;
    border-radius: 20px !important;
    font-weight: 500 !important;
    transition: all 0.15s !important;
}
[data-testid="stPills"] button[aria-selected="true"] {
    background: rgba(0,212,170,0.15) !important;
    border-color: #00d4aa !important;
    color: #00d4aa !important;
}

/* ── Code blocks ──────────────────────────────── */
.stCodeBlock { border-radius: 8px !important; }

/* ── Info / success / warning / error ─────────── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-width: 1px !important;
}

/* ── Toast ────────────────────────────────────── */
[data-testid="toastContainer"] { font-family: 'Inter', sans-serif !important; }

/* ── Responsive: Mobile ───────────────────────── */
@media (max-width: 640px) {
    .main .block-container { padding: 0.8rem 0.8rem 2rem !important; }
    h1 { font-size: 1.3rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
}

/* ── Custom badge classes ─────────────────────── */
.badge-buy {
    background: rgba(0,212,170,0.15);
    color: #00d4aa;
    border: 1px solid #00d4aa;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    display: inline-block;
}
.badge-watch {
    background: rgba(139,148,158,0.12);
    color: #8b949e;
    border: 1px solid #30363d;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    display: inline-block;
}
.badge-open {
    background: rgba(56,139,253,0.15);
    color: #388bfd;
    border: 1px solid #388bfd;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 700;
    display: inline-block;
}
.badge-closed-win {
    background: rgba(0,212,170,0.12);
    color: #00d4aa;
    border: 1px solid rgba(0,212,170,0.4);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    display: inline-block;
}
.badge-closed-loss {
    background: rgba(255,77,109,0.12);
    color: #ff4d6d;
    border: 1px solid rgba(255,77,109,0.4);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    display: inline-block;
}

/* ── Stat card ────────────────────────────────── */
.stat-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 16px 20px;
    transition: border-color 0.2s;
}
.stat-card:hover { border-color: #388bfd; }
.stat-label {
    font-size: 0.72rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 4px;
}
.stat-value {
    font-size: 1.45rem;
    font-weight: 700;
    color: #e6edf3;
    line-height: 1.2;
}
.stat-sub {
    font-size: 0.78rem;
    color: #8b949e;
    margin-top: 2px;
}
.positive { color: #00d4aa !important; }
.negative { color: #ff4d6d !important; }
.neutral  { color: #f5a623 !important; }

/* ── Trade card ───────────────────────────────── */
.trade-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    border-left: 4px solid #388bfd;
    transition: all 0.2s;
}
.trade-card:hover { border-color: #388bfd; box-shadow: 0 4px 20px rgba(56,139,253,0.1); }
.trade-card-win  { border-left-color: #00d4aa !important; }
.trade-card-loss { border-left-color: #ff4d6d !important; }
.trade-card-open { border-left-color: #388bfd !important; }
"""


def inject_css() -> None:
    """Call once per page to inject the dark theme."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def badge(label: str, kind: str = "buy") -> str:
    """Return an HTML badge string. kind: 'buy','watch','open','win','loss'"""
    cls = {
        "buy": "badge-buy",
        "watch": "badge-watch",
        "open": "badge-open",
        "win": "badge-closed-win",
        "loss": "badge-closed-loss",
    }.get(kind.lower(), "badge-watch")
    return f'<span class="{cls}">{label}</span>'


def stat_card_html(label: str, value: str, sub: str = "", color: str = "") -> str:
    color_cls = {"positive": "positive", "negative": "negative", "neutral": "neutral"}.get(color, "")
    return f"""
    <div class="stat-card">
        <div class="stat-label">{label}</div>
        <div class="stat-value {color_cls}">{value}</div>
        {"" if not sub else f'<div class="stat-sub">{sub}</div>'}
    </div>"""


def section_header(title: str, subtitle: str = "") -> None:
    """Render a styled section header."""
    sub_html = f"<p style='color:#8b949e;font-size:0.85rem;margin:0'>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"<div style='margin-bottom:16px'><h2 style='margin:0'>{title}</h2>{sub_html}</div>",
        unsafe_allow_html=True,
    )
