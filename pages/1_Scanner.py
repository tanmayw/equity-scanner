"""
pages/1_Scanner.py  —  Momentum Scanner
========================================
Scans Nifty indices for trend + momentum + volume + breakout setups.
BUY-signal stocks show an inline Trade Planner panel.
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Scanner · TrendMomentum", page_icon="📊", layout="wide")

from ui.styles import inject_css, badge
from ui.components import render_sidebar, render_trade_planner
from core.scanner_engine import (
    get_universe_tickers,
    run_scan,
    make_tradingview_url,
    NSE_INDEX_URLS,
)

inject_css()
settings = render_sidebar()
for k, v in settings.items():
    st.session_state[f"global_{k}"] = v

capital = settings["capital"]
risk_pct = settings["risk_pct"]
min_relvol = settings["min_relvol"]
rsi_threshold = settings["rsi_threshold"]

# ── Page header ───────────────────────────────────────────────────────────
st.markdown(
    "<h1>📊 Momentum Scanner</h1>"
    "<p style='color:#8b949e;margin-top:-8px'>Weekly + daily trend, RSI, volume breakout filter across Nifty universes.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Universe selector ─────────────────────────────────────────────────────
universe_options = list(NSE_INDEX_URLS.keys()) + ["Custom Watchlist"]
col_u, col_m = st.columns([3, 1])
with col_u:
    universe_choice = st.selectbox(
        "Select Universe",
        universe_options,
        index=0,
        label_visibility="collapsed",
    )
with col_m:
    scan_btn = st.button("🔄 Run Scanner", type="primary", use_container_width=True)

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

# ── Run scan ──────────────────────────────────────────────────────────────
if scan_btn:
    progress_bar = st.progress(0)
    status = st.empty()

    def _progress(done, total):
        pct = done / total
        progress_bar.progress(pct)
        status.caption(f"Scanning {done}/{total} stocks… ({int(pct*100)}%)")

    with st.spinner(""):
        result = run_scan(target_tickers, capital, risk_pct, min_relvol, rsi_threshold, _progress)

    progress_bar.empty()
    status.empty()

    if result.empty:
        st.warning("No data returned. Check your internet connection.")
    else:
        st.session_state["scan"] = result
        st.session_state["scanned_universe"] = f"{universe_choice} ({len(target_tickers)} stocks)"
        st.toast(f"✅ Scan complete — {len(result)} stocks evaluated", icon="📊")

# ── Results ───────────────────────────────────────────────────────────────
if "scan" not in st.session_state:
    st.info("👆 Select a universe and click **Run Scanner** to see setups.")
    st.stop()

out: pd.DataFrame = st.session_state["scan"]
buys = out[out["Signal"] == "BUY"]
watches = out[out["Signal"] == "WATCH"]
scanned_info = st.session_state.get("scanned_universe", "")

# ── Summary metrics ───────────────────────────────────────────────────────
rs_outperformers = len(out[out["RS Outperforming"] == True]) if "RS Outperforming" in out.columns else 0
m1, m2, m3, m4 = st.columns(4)
m1.metric("🟢 BUY Setups", len(buys))
m2.metric("👀 Watchlist", len(watches))
m3.metric("⚡ RS > Nifty 50", f"{rs_outperformers}/{len(out)}")
m4.metric("💰 Capital Deployed / Trade", f"₹{capital * risk_pct / 100:,.0f} risk")

st.divider()

# ── Filter ────────────────────────────────────────────────────────────────
col_f1, col_f2 = st.columns([2.5, 1.2])
with col_f1:
    filter_sym = st.text_input("🔍 Filter symbol", "", placeholder="e.g. RELIANCE, HDFC…").strip().upper()
with col_f2:
    default_rs = settings.get("rs_filter", False)
    filter_rs = st.checkbox("⚡ Only RS > Nifty 50", value=default_rs, help="Show only stocks with positive Mansfield Relative Strength against Nifty 50 (RS > 0)")

filtered = out.copy()
if filter_sym:
    filtered = filtered[filtered["Symbol"].str.contains(filter_sym, na=False)]
if filter_rs and "RS Outperforming" in filtered.columns:
    filtered = filtered[filtered["RS Outperforming"] == True]

filtered_buys = filtered[filtered["Signal"] == "BUY"]

# ── BUY setups ────────────────────────────────────────────────────────────
st.markdown("### 🟢 Qualifying BUY Setups")

if filtered_buys.empty:
    st.info("No qualifying BUY setups matching filters in the current scan. Cash is a valid position. 💰")
else:
    clean_syms = filtered_buys["Symbol"].tolist()

    if "selected_buy_symbol" not in st.session_state or st.session_state["selected_buy_symbol"] not in clean_syms:
        st.session_state["selected_buy_symbol"] = clean_syms[0]

    # Pills for quick stock switch
    active = st.session_state["selected_buy_symbol"]
    idx_default = clean_syms.index(active) if active in clean_syms else 0
    pill_sel = st.pills("⚡ Select for Trade Planner:", clean_syms, default=clean_syms[idx_default], key="scanner_pills")
    if pill_sel and pill_sel != st.session_state["selected_buy_symbol"]:
        st.session_state["selected_buy_symbol"] = pill_sel
        st.rerun()

    col_grid, col_plan = st.columns([1.6, 1.0], gap="large")

    # Grid — curated columns only, explicit height to prevent blank collapse
    with col_grid:
        GRID_COLS = ["Symbol", "Setup", "Score", "RS vs Nifty", "Price", "Entry", "Stop", "Target 1", "Daily RSI", "Rel Vol", "Qty", "Risk ₹"]
        display_df = filtered_buys[[c for c in GRID_COLS if c in filtered_buys.columns]].copy()
        display_df["Symbol"] = display_df["Symbol"].apply(make_tradingview_url)

        n_rows = len(display_df)
        grid_height = min(60 + n_rows * 40, 480)  # dynamic height, capped at 480px

        buy_event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=grid_height,
            column_config={
                "Symbol": st.column_config.LinkColumn(
                    "Symbol",
                    help="Click to open TradingView chart",
                    display_text=r"#(.*)",
                    pinned=True,
                ),
                "Score": st.column_config.ProgressColumn(
                    "Score",
                    format="%d",
                    min_value=0,
                    max_value=100,
                ),
                "RS vs Nifty": st.column_config.NumberColumn(
                    "RS vs Nifty",
                    help="Mansfield Relative Strength vs Nifty 50 (50D). Positive indicates outperforming benchmark.",
                    format="%.2f%%",
                ),
                "Price": st.column_config.NumberColumn("CMP ₹", format="%.2f"),
                "Entry": st.column_config.NumberColumn("Entry ₹", format="%.2f"),
                "Stop": st.column_config.NumberColumn("Stop ₹", format="%.2f"),
                "Target 1": st.column_config.NumberColumn("T1 ₹", format="%.2f"),
                "Daily RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
                "Rel Vol": st.column_config.NumberColumn("Rel Vol", format="%.2f"),
                "Qty": st.column_config.NumberColumn("Qty", format="%d"),
                "Risk ₹": st.column_config.NumberColumn("Risk ₹", format="%.0f"),
            },
            on_select="rerun",
            selection_mode="single-row",
            key="buy_grid_table",
        )

        # Row-click sync
        if (buy_event and hasattr(buy_event, "selection")
                and buy_event.selection and buy_event.selection.rows):
            sel_row = buy_event.selection.rows[0]
            if 0 <= sel_row < len(clean_syms):
                new_sym = clean_syms[sel_row]
                if new_sym != st.session_state.get("selected_buy_symbol"):
                    st.session_state["selected_buy_symbol"] = new_sym
                    st.rerun()

    # Trade Planner panel
    with col_plan:
        active_sym = st.session_state.get("selected_buy_symbol", clean_syms[0])
        if active_sym not in clean_syms:
            active_sym = clean_syms[0]
            st.session_state["selected_buy_symbol"] = active_sym

        row = filtered_buys[filtered_buys["Symbol"] == active_sym].iloc[0]
        entry_d = float(row.get("Entry", row["Price"]))
        stop_d = float(row.get("Stop", entry_d * 0.95))
        t1_d = float(row.get("Target 1", entry_d + 2 * max(0.01, entry_d - stop_d)))
        rs_d = float(row.get("RS vs Nifty", 0.0)) if pd.notna(row.get("RS vs Nifty")) else None

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
                key_prefix=f"scanner_{active_sym}",
                show_add_button=True,
                rs_val=rs_d,
            )

st.divider()

# ── Watchlist ─────────────────────────────────────────────────────────────
filtered_watches = filtered[filtered["Signal"] == "WATCH"]
with st.expander(f"👀 Watchlist — {len(filtered_watches)} stocks"):
    if filtered_watches.empty:
        st.info("No watchlist candidates.")
    else:
        WATCH_COLS = ["Symbol", "Setup", "Score", "RS vs Nifty", "Price", "Daily RSI", "Weekly RSI", "Rel Vol", "EMA20", "EMA50"]
        disp_w = filtered_watches[[c for c in WATCH_COLS if c in filtered_watches.columns]].copy()
        disp_w["Symbol"] = disp_w["Symbol"].apply(make_tradingview_url)
        w_height = min(60 + len(disp_w) * 40, 400)
        st.dataframe(
            disp_w,
            use_container_width=True,
            hide_index=True,
            height=w_height,
            column_config={
                "Symbol": st.column_config.LinkColumn(
                    "Symbol", display_text=r"#(.*)", pinned=True
                ),
                "Score": st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=100),
                "RS vs Nifty": st.column_config.NumberColumn("RS vs Nifty", format="%.2f%%"),
                "Price": st.column_config.NumberColumn("CMP ₹", format="%.2f"),
                "Daily RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
                "Rel Vol": st.column_config.NumberColumn("Rel Vol", format="%.2f"),
            },
        )

# ── Download ──────────────────────────────────────────────────────────────
st.download_button("📥 Download Full Scan CSV", out.to_csv(index=False), "scanner.csv", "text/csv")
