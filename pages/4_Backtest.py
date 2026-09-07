"""
pages/4_Backtest.py  —  Historical Strategy Backtest
=====================================================
Test the Trend Momentum 4 strategy on a chosen NSE ticker
with real costs (commission + slippage). Shows equity curve,
monthly returns, and per-trade scatter.
"""

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Backtest · TrendMomentum", page_icon="🧪", layout="wide")

from ui.styles import inject_css
from ui.components import render_sidebar, plot_backtest_equity, plot_trade_scatter
from core.scanner_engine import get_history
from core.indicators import backtest

inject_css()
settings = render_sidebar()
capital = settings["capital"]
risk_pct = settings["risk_pct"]

# ── Page header ───────────────────────────────────────────────────────────
st.markdown(
    "<h1>🧪 Strategy Backtest</h1>"
    "<p style='color:#8b949e;margin-top:-8px'>"
    "Test the Trend Momentum rules on any NSE stock with realistic costs.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Controls ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
with c1:
    ticker = st.text_input("NSE Ticker", "RELIANCE.NS", placeholder="e.g. SBIN.NS, INFY.NS")
    if not ticker.upper().endswith(".NS"):
        ticker = ticker.strip().upper() + ".NS"
with c2:
    period = st.selectbox("History", ["2y", "5y", "10y"], index=1)
with c3:
    commission = st.number_input("Commission (bps, one-way)", 5.0, 100.0, 10.0, 1.0)
with c4:
    slippage = st.number_input("Slippage (bps, one-way)", 0.0, 100.0, 5.0, 1.0)

run_btn = st.button("▶ Run Backtest", type="primary")

# ── Run ───────────────────────────────────────────────────────────────────
if run_btn:
    with st.spinner(f"Running backtest on {ticker}…"):
        df = get_history(ticker, period, "1d")
        if df.empty:
            st.error(f"No data found for {ticker}. Check the symbol.")
            st.stop()
        trades, stats = backtest(df, capital, risk_pct, commission, slippage)

    if not stats or stats.get("trades", 0) == 0:
        st.warning("No qualifying trades found in the selected period. Strategy requires trend + RSI + volume + breakout conditions to align.")
        st.stop()

    st.session_state["bt_trades"] = trades
    st.session_state["bt_stats"] = stats
    st.session_state["bt_ticker"] = ticker
    st.session_state["bt_capital"] = capital
    st.toast(f"✅ Backtest complete — {stats['trades']} trades", icon="🧪")

# ── Results ───────────────────────────────────────────────────────────────
if "bt_stats" not in st.session_state:
    st.info("Enter a ticker and click **Run Backtest** to see results.")
    st.stop()

stats = st.session_state["bt_stats"]
trades: pd.DataFrame = st.session_state["bt_trades"]
bt_ticker = st.session_state.get("bt_ticker", ticker)
bt_capital = st.session_state.get("bt_capital", capital)

# ── Summary metrics ───────────────────────────────────────────────────────
st.markdown(f"### 📊 Results — {bt_ticker}")

m1, m2, m3, m4, m5, m6 = st.columns(6)
ret_color = "normal" if stats["return_pct"] >= 0 else "inverse"
m1.metric("Total Return", f"{stats['return_pct']:+.1f}%", delta_color=ret_color)
m2.metric("Final Capital", f"₹{stats['final']:,.0f}")
m3.metric("Max Drawdown", f"{stats['max_dd_pct']:.1f}%", delta_color="off")
m4.metric("Win Rate", f"{stats['win_rate']:.1f}%")
m5.metric("Profit Factor", f"{stats['profit_factor']:.2f}")
m6.metric("Total Trades", stats["trades"])

m7, m8 = st.columns([1, 5])
m7.metric("Avg R / Trade", f"{stats.get('avg_R', 0):.2f}R")

st.divider()

# ── Equity curve ──────────────────────────────────────────────────────────
st.markdown("### 📈 Equity Curve")
eq = stats.get("equity")
if eq is not None and not eq.empty:
    plot_backtest_equity(eq["Equity"], bt_capital)

st.divider()

# ── Trade scatter ─────────────────────────────────────────────────────────
col_scatter, col_table = st.columns([1, 1.5])

with col_scatter:
    st.markdown("### 🎯 Trade R-Multiple Distribution")
    plot_trade_scatter(trades)

with col_table:
    st.markdown("### 📋 Trade Log")
    disp_trades = trades.copy()
    disp_trades["Entry Date"] = pd.to_datetime(disp_trades["Entry Date"]).dt.strftime("%d %b %Y")
    disp_trades["Exit Date"] = pd.to_datetime(disp_trades["Exit Date"]).dt.strftime("%d %b %Y")
    st.dataframe(
        disp_trades[["Entry Date", "Exit Date", "Entry", "Exit", "Qty", "PnL", "R", "Reason"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Entry": st.column_config.NumberColumn("Entry ₹", format="%.2f"),
            "Exit": st.column_config.NumberColumn("Exit ₹", format="%.2f"),
            "PnL": st.column_config.NumberColumn("P&L ₹", format="₹%.0f"),
            "R": st.column_config.NumberColumn("R", format="%.2f"),
        },
        height=280,
    )

st.divider()

# ── Monthly breakdown ─────────────────────────────────────────────────────
st.markdown("### 📅 Monthly P&L Breakdown")
if not trades.empty:
    trades_copy = trades.copy()
    trades_copy["Exit Date"] = pd.to_datetime(trades_copy["Exit Date"])
    trades_copy["Month"] = trades_copy["Exit Date"].dt.to_period("M")
    monthly = trades_copy.groupby("Month").agg(
        Trades=("PnL", "count"),
        Wins=("PnL", lambda x: (x > 0).sum()),
        PnL=("PnL", "sum"),
        AvgR=("R", "mean"),
    ).reset_index()
    monthly["Win%"] = (monthly["Wins"] / monthly["Trades"] * 100).round(1)
    monthly["Month"] = monthly["Month"].astype(str)
    st.dataframe(
        monthly[["Month", "Trades", "Wins", "Win%", "PnL", "AvgR"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "PnL": st.column_config.NumberColumn("Net P&L ₹", format="₹%.0f"),
            "Win%": st.column_config.NumberColumn("Win %", format="%.1f%%"),
            "AvgR": st.column_config.NumberColumn("Avg R", format="%.2f"),
        },
    )

st.download_button(
    "📥 Download Trade Log CSV",
    trades.to_csv(index=False),
    f"backtest_{bt_ticker}.csv",
    "text/csv",
)
