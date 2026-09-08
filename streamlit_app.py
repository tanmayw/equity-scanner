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

from core.paper_book import load_trades
try:
    p_df = load_trades()
    n_open_trades = len(p_df[p_df["status"] == "OPEN"]) if not p_df.empty else 0
except Exception:
    n_open_trades = 0

st.divider()

if n_open_trades > 0:
    st.markdown(
        f"""<div style='background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.3);border-radius:10px;padding:12px 18px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between'>
            <span>📋 <b>Paper Portfolio:</b> You have <b style='color:#00d4aa'>{n_open_trades} active open position{'s' if n_open_trades != 1 else ''}</b> saved on disk.</span>
            <a href='/Paper_Trading' target='_self' style='color:#00d4aa;font-weight:600;font-size:0.85rem;text-decoration:none'>Manage Open Positions →</a>
        </div>""",
        unsafe_allow_html=True,
    )

# ── Quick-nav cards ───────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

paper_desc = f"Track simulated trades · {n_open_trades} Open" if n_open_trades > 0 else "Track simulated trades & monthly performance"

nav_cards = [
    ("📊", "Scanner", "Scan Nifty universes for breakout & momentum setups", "pages/1_Scanner.py", "/Scanner"),
    ("🎯", "Trade Planner", "Calculate position size, R:R, and order details", "pages/2_Trade_Planner.py", "/Trade_Planner"),
    ("📋", "Paper Trading", paper_desc, "pages/3_Paper_Trading.py", "/Paper_Trading"),
    ("🧪", "Backtest", "Test strategy on historical data with real costs", "pages/4_Backtest.py", "/Backtest"),
    ("📘", "Rules", "System rules for entries, exits, and risk management", "pages/5_Rules.py", "/Rules"),
]


for col, (icon, title, desc, page_path, route) in zip([c1, c2, c3, c4, c5], nav_cards):
    with col:
        st.markdown(
            f"""<a href="{route}" target="_self" style="text-decoration:none; color:inherit; display:block;">
                <div class='stat-card' style='text-align:center;cursor:pointer;min-height:140px;transition:transform 0.18s ease, border-color 0.18s ease;'>
                    <p style='font-size:2rem;margin:0 0 8px'>{icon}</p>
                    <p style='font-weight:700;color:#e6edf3;margin:0 0 4px;font-size:1rem'>{title}</p>
                    <p style='color:#8b949e;font-size:0.75rem;margin:0 0 10px;line-height:1.4'>{desc}</p>
                    <span style='font-size:0.78rem;color:#00d4aa;font-weight:600'>Open →</span>
                </div>
            </a>""",
            unsafe_allow_html=True,
        )
        if st.button(f"Launch {title}", key=f"btn_nav_{title}", use_container_width=True):
            st.switch_page(page_path)


st.divider()

# ── Disclaimer ────────────────────────────────────────────────────────────
st.markdown(
    "<p style='color:#8b949e;font-size:0.75rem;text-align:center'>"
    "⚠️ This tool is for educational and research purposes only. "
    "Past performance does not guarantee future results. Not SEBI-registered investment advice."
    "</p>",
    unsafe_allow_html=True,
)
