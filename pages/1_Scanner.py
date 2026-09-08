"""
pages/1_Scanner.py  —  Momentum Scanner
========================================
Tab 1: Breakout + momentum setups (existing).
Tab 2: 20 EMA Pullback setups — confirmed bullish bounce on the 20 EMA.
BUY-signal stocks show an inline Trade Planner panel in both tabs.
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

st.set_page_config(page_title="Scanner · TrendMomentum", page_icon="📊", layout="wide")

import importlib
import core.indicators
import core.scanner_engine

try:
    importlib.reload(core.indicators)
except Exception:
    pass

try:
    importlib.reload(core.scanner_engine)
except Exception:
    pass

from ui.styles import inject_css, badge
from ui.components import render_sidebar, render_trade_planner
from core.scanner_engine import (
    get_universe_tickers,
    run_scan,
    make_tradingview_url,
    NSE_INDEX_URLS,
)

try:
    from core.scanner_engine import run_pullback_scan
except ImportError:
    # Warm process fallback: force re-reload and import
    try:
        importlib.reload(core.indicators)
        importlib.reload(core.scanner_engine)
        from core.scanner_engine import run_pullback_scan
    except Exception:
        def run_pullback_scan(*args, **kwargs):
            return pd.DataFrame()

inject_css()
settings = render_sidebar()
for k, v in settings.items():
    st.session_state[f"global_{k}"] = v

capital       = settings["capital"]
risk_pct      = settings["risk_pct"]
min_relvol    = settings["min_relvol"]
rsi_threshold = settings["rsi_threshold"]

# ── Page header ───────────────────────────────────────────────────────────
st.markdown(
    "<h1>📊 Scanner</h1>"
    "<p style='color:#8b949e;margin-top:-8px'>"
    "Momentum Breakout & 20 EMA Pullback setups across Nifty universes.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Shared universe selector ──────────────────────────────────────────────
universe_options = list(NSE_INDEX_URLS.keys()) + ["Custom Watchlist"]
col_u, col_dummy = st.columns([4, 1])
with col_u:
    universe_choice = st.selectbox(
        "Select Universe",
        universe_options,
        index=0,
        label_visibility="collapsed",
    )

if universe_choice == "Custom Watchlist":
    custom_input = st.text_area(
        "NSE symbols (comma/space separated)",
        value="UNIONBANK, TATAPOWER, SBIN, IRFC, BEL",
        height=68,
    )
    raw_syms = [s.strip().upper() for s in custom_input.replace("\n", ",").split(",") if s.strip()]
    target_tickers = [s if (s.endswith(".NS") or s.endswith(".BO")) else f"{s}.NS" for s in raw_syms]
else:
    target_tickers = get_universe_tickers(universe_choice)

st.caption(f"Universe: **{universe_choice}** · {len(target_tickers)} stocks loaded")
st.divider()

# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════
tab_breakout, tab_pullback = st.tabs([
    "📊 Momentum Breakout",
    "🔄 20 EMA Pullback",
])


# ─────────────────────────────────────────────────────────────────────────
# Helper — shared results display (reused by both tabs)
# ─────────────────────────────────────────────────────────────────────────
def _render_results(
    out: pd.DataFrame,
    scan_key: str,
    capital: float,
    risk_pct: float,
    settings: dict,
    grid_cols: list,
    tab_label: str,
) -> None:
    buys    = out[out["Signal"] == "BUY"]
    watches = out[out["Signal"] == "WATCH"]
    rs_out  = (
        len(out[out["RS Outperforming"] == True])
        if "RS Outperforming" in out.columns else 0
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🟢 BUY Setups",             len(buys))
    m2.metric("👀 Watchlist",               len(watches))
    m3.metric("⚡ RS > Nifty 50",           f"{rs_out}/{len(out)}")
    m4.metric("💰 Capital Deployed / Trade", f"₹{capital * risk_pct / 100:,.0f} risk")
    st.divider()

    col_f1, col_f2 = st.columns([2.5, 1.2])
    with col_f1:
        filter_sym = st.text_input(
            "🔍 Filter symbol", "", placeholder="e.g. RELIANCE, HDFC…",
            key=f"{scan_key}_filter_sym",
        ).strip().upper()
    with col_f2:
        filter_rs = st.checkbox(
            "⚡ Only RS > Nifty 50", value=settings.get("rs_filter", False),
            help="Show only stocks outperforming Nifty 50 (RS > 0)",
            key=f"{scan_key}_filter_rs",
        )

    filtered = out.copy()
    if filter_sym:
        filtered = filtered[filtered["Symbol"].str.contains(filter_sym, na=False)]
    if filter_rs and "RS Outperforming" in filtered.columns:
        filtered = filtered[filtered["RS Outperforming"] == True]

    filtered_buys   = filtered[filtered["Signal"] == "BUY"]
    filtered_watches = filtered[filtered["Signal"] == "WATCH"]

    st.markdown("### 🟢 Qualifying BUY Setups")

    if filtered_buys.empty:
        st.info("No qualifying BUY setups matching filters. Cash is a valid position. 💰")
    else:
        clean_syms = filtered_buys["Symbol"].tolist()
        sel_key    = f"{scan_key}_selected_sym"

        if sel_key not in st.session_state or st.session_state[sel_key] not in clean_syms:
            st.session_state[sel_key] = clean_syms[0]

        active      = st.session_state[sel_key]
        idx_default = clean_syms.index(active) if active in clean_syms else 0
        pill_sel    = st.pills(
            "⚡ Select for Trade Planner:",
            clean_syms,
            default=clean_syms[idx_default],
            key=f"{scan_key}_pills",
        )
        if pill_sel and pill_sel != st.session_state[sel_key]:
            st.session_state[sel_key] = pill_sel
            st.rerun()

        col_grid, col_plan = st.columns([1.6, 1.0], gap="large")

        with col_grid:
            avail_cols  = [c for c in grid_cols if c in filtered_buys.columns]
            display_df  = filtered_buys[avail_cols].copy()
            display_df["Symbol"] = display_df["Symbol"].apply(make_tradingview_url)
            n_rows      = len(display_df)
            grid_height = min(60 + n_rows * 40, 480)

            col_config = {
                "Symbol": st.column_config.LinkColumn(
                    "Symbol", help="Click to open TradingView chart",
                    display_text=r"#(.*)", pinned=True,
                ),
                "Score": st.column_config.ProgressColumn(
                    "Score", format="%d", min_value=0, max_value=100,
                ),
                "RS vs Nifty": st.column_config.NumberColumn(
                    "RS vs Nifty",
                    help="Mansfield RS vs Nifty 50. Positive = outperforming.",
                    format="%.2f%%",
                ),
                "Price":     st.column_config.NumberColumn("CMP ₹",   format="%.2f"),
                "EMA20":     st.column_config.NumberColumn("EMA20 ₹",  format="%.2f"),
                "Entry":     st.column_config.NumberColumn("Entry ₹",  format="%.2f"),
                "Stop":      st.column_config.NumberColumn("Stop ₹",   format="%.2f"),
                "Target 1":  st.column_config.NumberColumn("T1 ₹",    format="%.2f"),
                "Target 2":  st.column_config.NumberColumn("T2 ₹",    format="%.2f"),
                "Daily RSI": st.column_config.NumberColumn("RSI",      format="%.1f"),
                "Rel Vol":   st.column_config.NumberColumn("Rel Vol",  format="%.2f"),
                "Qty":       st.column_config.NumberColumn("Qty",       format="%d"),
                "Risk ₹":    st.column_config.NumberColumn("Risk ₹",   format="%.0f"),
            }

            grid_event = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=grid_height,
                column_config=col_config,
                on_select="rerun",
                selection_mode="single-row",
                key=f"{scan_key}_grid_table",
            )

            if (grid_event and hasattr(grid_event, "selection")
                    and grid_event.selection and grid_event.selection.rows):
                sel_row = grid_event.selection.rows[0]
                if 0 <= sel_row < len(clean_syms):
                    new_sym = clean_syms[sel_row]
                    if new_sym != st.session_state.get(sel_key):
                        st.session_state[sel_key] = new_sym
                        st.rerun()

        with col_plan:
            active_sym = st.session_state.get(sel_key, clean_syms[0])
            if active_sym not in clean_syms:
                active_sym = clean_syms[0]
                st.session_state[sel_key] = active_sym

            row     = filtered_buys[filtered_buys["Symbol"] == active_sym].iloc[0]
            entry_d = float(row.get("Entry", row["Price"]))
            stop_d  = float(row.get("Stop",  entry_d * 0.95))
            t1_d    = float(row.get("Target 1", entry_d + 2 * max(0.01, entry_d - stop_d)))
            rs_d    = float(row.get("RS vs Nifty", 0.0)) if pd.notna(row.get("RS vs Nifty")) else None

            with st.container(border=True):
                render_trade_planner(
                    symbol=active_sym,
                    entry_default=entry_d,
                    stop_default=stop_d,
                    target1_default=t1_d,
                    setup=str(row.get("Setup", "Trend")),
                    score=int(row.get("Score", 80)),
                    cmp=float(row["Price"]),
                    capital=capital,
                    risk_pct=risk_pct,
                    key_prefix=f"{scan_key}_{active_sym}",
                    show_add_button=True,
                    rs_val=rs_d,
                )

    st.divider()

    WATCH_COLS = ["Symbol", "Setup", "Score", "RS vs Nifty", "Price", "EMA20",
                  "Daily RSI", "Weekly RSI", "Rel Vol"]
    with st.expander(f"👀 Watchlist — {len(filtered_watches)} stocks"):
        if filtered_watches.empty:
            st.info("No watchlist candidates.")
        else:
            avail_w = [c for c in WATCH_COLS if c in filtered_watches.columns]
            disp_w  = filtered_watches[avail_w].copy()
            disp_w["Symbol"] = disp_w["Symbol"].apply(make_tradingview_url)
            w_height = min(60 + len(disp_w) * 40, 400)
            st.dataframe(
                disp_w,
                use_container_width=True,
                hide_index=True,
                height=w_height,
                column_config={
                    "Symbol":    st.column_config.LinkColumn("Symbol", display_text=r"#(.*)", pinned=True),
                    "Score":     st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=100),
                    "RS vs Nifty": st.column_config.NumberColumn("RS vs Nifty", format="%.2f%%"),
                    "Price":     st.column_config.NumberColumn("CMP ₹",   format="%.2f"),
                    "EMA20":     st.column_config.NumberColumn("EMA20 ₹", format="%.2f"),
                    "Daily RSI": st.column_config.NumberColumn("RSI",     format="%.1f"),
                    "Rel Vol":   st.column_config.NumberColumn("Rel Vol", format="%.2f"),
                },
            )

    st.download_button(
        f"📥 Download {tab_label} CSV",
        out.to_csv(index=False),
        f"{scan_key}_scan.csv",
        "text/csv",
        key=f"{scan_key}_dl",
    )


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — MOMENTUM BREAKOUT
# ════════════════════════════════════════════════════════════════════════════
with tab_breakout:
    col_hdr, col_btn = st.columns([5, 1])
    with col_hdr:
        st.markdown(
            "**📊 Momentum Breakout** — Weekly + daily trend, RSI, volume & price breakout filter.",
        )
    with col_btn:
        scan_btn = st.button("🔄 Run Scan", type="primary", use_container_width=True, key="breakout_run")

    if scan_btn:
        prog = st.progress(0)
        stat = st.empty()

        def _prog_breakout(done, total):
            pct = done / total
            prog.progress(pct)
            stat.caption(f"Scanning {done}/{total} stocks… ({int(pct*100)}%)")

        with st.spinner(""):
            result = run_scan(target_tickers, capital, risk_pct, min_relvol, rsi_threshold, _prog_breakout)

        prog.empty(); stat.empty()

        if result.empty:
            st.warning("No data returned. Check your internet connection.")
        else:
            st.session_state["scan_breakout"] = result
            st.session_state["scan_breakout_universe"] = f"{universe_choice} ({len(target_tickers)})"
            st.toast(f"✅ Scan complete — {len(result)} stocks evaluated", icon="📊")

    if "scan_breakout" not in st.session_state:
        st.info("👆 Click **Run Scan** to find momentum breakout setups.")
    else:
        st.caption(f"Universe: {st.session_state.get('scan_breakout_universe', '')}")
        BREAKOUT_COLS = ["Symbol", "Setup", "Score", "RS vs Nifty", "Price",
                         "Entry", "Stop", "Target 1", "Daily RSI", "Rel Vol", "Qty", "Risk ₹"]
        _render_results(
            out=st.session_state["scan_breakout"],
            scan_key="breakout",
            capital=capital,
            risk_pct=risk_pct,
            settings=settings,
            grid_cols=BREAKOUT_COLS,
            tab_label="Breakout",
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — 20 EMA PULLBACK SCANNER
# ════════════════════════════════════════════════════════════════════════════
with tab_pullback:
    col_hdr2, col_btn2 = st.columns([5, 1])
    with col_hdr2:
        st.markdown(
            "**🔄 20 EMA Pullback** — Uptrend intact · Stock dipped to 20 EMA · "
            "Confirmed with a bullish bounce candle.",
        )
    with col_btn2:
        pullback_btn = st.button("🔄 Run Scan", type="primary", use_container_width=True, key="pullback_run")

    with st.expander("ℹ️ How the pullback scanner works", expanded=False):
        st.markdown("""
**20 EMA Pullback Setup — criteria:**

| # | Condition | Detail |
|---|-----------|--------|
| 1 | **Uptrend** | Daily: Close > EMA20 > EMA50 |
| 2 | **Weekly trend** | W-Close > W-EMA20, W-RSI > 55 |
| 3 | **Pullback touch** | Within last 3 bars: candle Low ≤ EMA20 ≤ High, or Close within 0.5% of EMA20 |
| 4 | **Bullish confirmation** | Bar *after* the touch: Close > Open AND Close > EMA20 |
| 5 | **RSI zone** | Daily RSI 40–70 on confirmation bar |

**Stop** → Below the pullback candle's Low &nbsp;|&nbsp;
**Target 1** → Entry + 2R &nbsp;|&nbsp; **Target 2** → Entry + 3R

> *Volume on the confirmation candle adds to the score but does not disqualify.*
        """)

    if pullback_btn:
        prog2 = st.progress(0)
        stat2 = st.empty()

        def _prog_pullback(done, total):
            pct = done / total
            prog2.progress(pct)
            stat2.caption(f"Scanning {done}/{total} stocks… ({int(pct*100)}%)")

        with st.spinner(""):
            result2 = run_pullback_scan(
                target_tickers, capital, risk_pct, min_relvol, _prog_pullback
            )

        prog2.empty(); stat2.empty()

        if result2.empty:
            st.warning("No pullback setups found in this universe right now.")
        else:
            st.session_state["scan_pullback"] = result2
            st.session_state["scan_pullback_universe"] = f"{universe_choice} ({len(target_tickers)})"
            buys_found = len(result2[result2["Signal"] == "BUY"])
            st.toast(f"✅ Pullback scan — {buys_found} BUY setups found", icon="🔄")

    if "scan_pullback" not in st.session_state:
        st.info("👆 Click **Run Scan** to find 20 EMA pullback setups.")
    else:
        st.caption(f"Universe: {st.session_state.get('scan_pullback_universe', '')}")
        PULLBACK_COLS = ["Symbol", "Setup", "Score", "RS vs Nifty", "Price", "EMA20",
                         "Entry", "Stop", "Target 1", "Target 2", "Daily RSI", "Rel Vol", "Qty", "Risk ₹"]
        _render_results(
            out=st.session_state["scan_pullback"],
            scan_key="pullback",
            capital=capital,
            risk_pct=risk_pct,
            settings=settings,
            grid_cols=PULLBACK_COLS,
            tab_label="EMA Pullback",
        )
