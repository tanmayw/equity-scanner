"""
streamlit_app.py  —  TrendMomentum 4 · Main Entry Point
=========================================================
Professional Indian Equity Swing Trading Platform.

Architecture
------------
  pages/1_Scanner.py        – Momentum scanner
  pages/2_Trade_Planner.py  – Full position planner
  pages/3_Paper_Trading.py  – Paper trade journal
  pages/4_Backtest.py       – Historical strategy test
  pages/5_Rules.py          – System trading rules

  core/indicators.py        – RSI, ATR, EMA, signal_for, backtest
  core/scanner_engine.py    – Universe loader, parallel scan
  core/paper_book.py        – Paper trade CRUD + analytics

  ui/styles.py              – Dark-theme CSS injection
  ui/components.py          – Shared Plotly charts + widgets
"""

import streamlit as st

st.set_page_config(
    page_title="TrendMomentum 4",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "TrendMomentum 4 — Indian Equity Swing System\nRules-based research tool. Not investment advice.",
    },
)

# ── Inject global dark-theme CSS ─────────────────────────────────────────
from ui.styles import inject_css
inject_css()

# ── Sidebar (shared settings) ────────────────────────────────────────────
from ui.components import render_sidebar
settings = render_sidebar()

# Persist to session_state so all pages can read them
for k, v in settings.items():
    st.session_state[f"global_{k}"] = v

# ── Landing hero ──────────────────────────────────────────────────────────
st.markdown(
    """
    <div style='text-align:center;padding:60px 20px 20px'>
        <p style='font-size:3rem;margin:0'>📈</p>
        <h1 style='font-size:2.4rem;font-weight:800;
                   background:linear-gradient(135deg,#00d4aa,#388bfd);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                   background-clip:text;margin:8px 0 12px'>
            TrendMomentum 4
        </h1>
        <p style='color:#8b949e;font-size:1.05rem;max-width:560px;margin:0 auto'>
            Professional Indian equity swing trading platform — scanner, trade planner,
            paper trading journal, and backtest engine in one app.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

# ── Quick-nav cards ───────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

nav_cards = [
    ("📊", "Scanner", "Scan Nifty universes for breakout & momentum setups", "pages/1_Scanner"),
    ("🎯", "Trade Planner", "Calculate position size, R:R, and order details", "pages/2_Trade_Planner"),
    ("📋", "Paper Trading", "Track simulated trades & monthly performance", "pages/3_Paper_Trading"),
    ("🧪", "Backtest", "Test strategy on historical data with real costs", "pages/4_Backtest"),
    ("📘", "Rules", "System rules for entries, exits, and risk management", "pages/5_Rules"),
]

for col, (icon, title, desc, _) in zip([c1, c2, c3, c4, c5], nav_cards):
    with col:
        st.markdown(
            f"""<div class='stat-card' style='text-align:center;cursor:pointer;min-height:130px'>
                <p style='font-size:1.8rem;margin:0 0 8px'>{icon}</p>
                <p style='font-weight:700;color:#e6edf3;margin:0 0 4px;font-size:0.95rem'>{title}</p>
                <p style='color:#8b949e;font-size:0.75rem;margin:0;line-height:1.4'>{desc}</p>
            </div>""",
            unsafe_allow_html=True,
        )

st.divider()

# ── Disclaimer ────────────────────────────────────────────────────────────
st.markdown(
    "<p style='color:#8b949e;font-size:0.75rem;text-align:center'>"
    "⚠️ This tool is for educational and research purposes only. "
    "Past performance does not guarantee future results. Not SEBI-registered investment advice."
    "</p>",
    unsafe_allow_html=True,
)
