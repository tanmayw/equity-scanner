"""
pages/2_Trade_Planner.py  —  Full Trade Planner
================================================
Manual trade planning with stock search, full position sizing,
R:R dashboard, and one-click Add to Paper Book.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Trade Planner · TrendMomentum", page_icon="🎯", layout="wide")

from ui.styles import inject_css, badge
from ui.components import render_sidebar, render_trade_planner
from core.scanner_engine import get_history, make_tradingview_url

inject_css()
settings = render_sidebar()
capital = settings["capital"]
risk_pct = settings["risk_pct"]

# ── Page header ───────────────────────────────────────────────────────────
st.markdown(
    "<h1>🎯 Trade Planner</h1>"
    "<p style='color:#8b949e;margin-top:-8px'>Plan your trade before you take it. "
    "Calculate position size, risk, reward, and generate your order ticket.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Source selector ───────────────────────────────────────────────────────
# Option A: Load from last scan results
scan_buys = []
if "scan" in st.session_state and not st.session_state["scan"].empty:
    scan_buys = (
        st.session_state["scan"][st.session_state["scan"]["Signal"] == "BUY"]["Symbol"]
        .tolist()
    )

tab_scan, tab_manual = st.tabs(["📊 Load from Scanner", "✏️ Manual Entry"])

# ── Tab 1: From Scanner ────────────────────────────────────────────────────
with tab_scan:
    if not scan_buys:
        st.info("No scanner results found. Go to **Scanner** and run a scan first, then come back.")
    else:
        sel_sym = st.pills("Select Stock", scan_buys, default=scan_buys[0], key="planner_pills")

        if sel_sym:
            row = st.session_state["scan"][
                st.session_state["scan"]["Signal"] == "BUY"
            ]
            row = row[row["Symbol"] == sel_sym]
            if not row.empty:
                r = row.iloc[0]
                entry_d = float(r.get("Entry", r["Price"]))
                stop_d = float(r.get("Stop", entry_d * 0.95))
                t1_d = float(r.get("Target 1", entry_d + 2 * max(0.01, entry_d - stop_d)))

                render_trade_planner(
                    symbol=sel_sym,
                    entry_default=entry_d,
                    stop_default=stop_d,
                    target1_default=t1_d,
                    setup=str(r.get("Setup", "Trend")),
                    score=int(r.get("Score", 80)),
                    cmp=float(r["Price"]),
                    capital=capital,
                    risk_pct=risk_pct,
                    key_prefix=f"planner_scan_{sel_sym}",
                    show_add_button=True,
                )

# ── Tab 2: Manual Entry ────────────────────────────────────────────────────
with tab_manual:
    st.markdown("##### Enter stock details manually")
    col_sym, col_setup = st.columns([2, 2])
    with col_sym:
        manual_sym = st.text_input("NSE Symbol", value="RELIANCE", placeholder="e.g. SBIN, TATAPOWER").strip().upper()
    with col_setup:
        setup_options = ["Breakout", "Trend", "Pullback", "Reversal", "Other"]
        manual_setup = st.selectbox("Setup Type", setup_options)

    st.markdown("---")

    # Try to pre-fill CMP from yfinance
    cmp_live = None
    col_fetch, col_note = st.columns([1, 3])
    with col_fetch:
        if st.button("📡 Fetch Live Price", key="fetch_cmp"):
            with st.spinner(f"Fetching {manual_sym}..."):
                try:
                    ticker_sym = manual_sym if manual_sym.endswith(".NS") else f"{manual_sym}.NS"
                    df_live = get_history(ticker_sym, "5d", "1d")
                    if not df_live.empty:
                        cmp_live = float(df_live["Close"].iloc[-1])
                        st.session_state["manual_cmp"] = cmp_live
                        st.toast(f"₹{cmp_live:,.2f} loaded for {manual_sym}", icon="📡")
                except Exception:
                    st.warning("Could not fetch price. Enter manually below.")
    with col_note:
        if "manual_cmp" in st.session_state:
            st.info(f"Last fetched CMP: ₹{st.session_state['manual_cmp']:,.2f}")

    cmp_val = st.session_state.get("manual_cmp", 1000.0)

    # Default stop = 3% below CMP
    default_stop = round(cmp_val * 0.97, 2)
    default_t1 = round(cmp_val + 2 * (cmp_val - default_stop), 2)

    render_trade_planner(
        symbol=manual_sym,
        entry_default=float(cmp_val),
        stop_default=float(default_stop),
        target1_default=float(default_t1),
        setup=manual_setup,
        score=80,
        cmp=float(cmp_val),
        capital=capital,
        risk_pct=risk_pct,
        key_prefix="planner_manual",
        show_add_button=True,
    )

st.divider()

# ── Paper Book quick-link ────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;padding:8px'>"
    "<p style='color:#8b949e;font-size:0.85rem'>"
    "Trades added here go to the <b style='color:#388bfd'>Paper Trading Journal</b> "
    "where you can track P&L and simulate monthly performance.</p>"
    "</div>",
    unsafe_allow_html=True,
)
