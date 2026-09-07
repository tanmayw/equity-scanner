"""
ui/components.py
-----------------
Reusable Streamlit UI components for the trading platform.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from ui.styles import badge, stat_card_html


# ---------------------------------------------------------------------------
# Sidebar — global settings
# ---------------------------------------------------------------------------

def render_sidebar() -> dict:
    """
    Renders the sidebar with capital/risk settings.
    Returns a dict of: capital, risk_pct, max_positions, min_relvol, rsi_threshold.
    """
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center;padding:12px 0 8px'>"
            "<span style='font-size:1.6rem'>📈</span>"
            "<p style='color:#e6edf3;font-weight:700;font-size:1.1rem;margin:4px 0 0'>TrendMomentum</p>"
            "<p style='color:#8b949e;font-size:0.72rem;margin:0'>Indian Equity Swing System</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        st.markdown("**⚙️ Capital & Risk**")
        capital = st.number_input("Portfolio Capital (₹)", 50_000, 10_000_000, 200_000, 10_000)
        risk_pct = st.slider("Risk per Trade (%)", 0.1, 2.0, 0.5, 0.1)
        max_positions = st.number_input("Max Simultaneous Positions", 1, 10, 3)

        st.divider()
        st.markdown("**🎛️ Signal Filters**")
        min_relvol = st.slider("Min Relative Volume", 1.0, 3.0, 1.5, 0.1)
        rsi_threshold = st.slider("Daily RSI Threshold", 50, 70, 55)

        st.divider()
        st.markdown(
            "<p style='color:#8b949e;font-size:0.72rem;line-height:1.5'>"
            "Rules-based research tool.<br>Not investment advice."
            "</p>",
            unsafe_allow_html=True,
        )

    return {
        "capital": capital,
        "risk_pct": risk_pct,
        "max_positions": max_positions,
        "min_relvol": min_relvol,
        "rsi_threshold": rsi_threshold,
    }


# ---------------------------------------------------------------------------
# Trade Planner widget
# ---------------------------------------------------------------------------

def render_trade_planner(
    symbol: str,
    entry_default: float,
    stop_default: float,
    target1_default: float,
    setup: str = "Trend",
    score: int = 80,
    cmp: float = None,
    capital: float = 200_000,
    risk_pct: float = 0.5,
    key_prefix: str = "tp",
    show_add_button: bool = True,
) -> dict:
    """
    Full Trade Planner card. Returns the current trade parameters as dict.
    If user clicks 'Add to Paper Book', also returns add_triggered=True.
    """
    from core.scanner_engine import make_tradingview_url
    from core.paper_book import add_trade

    import math

    def _safe_float(val, fallback: float) -> float:
        try:
            f = float(val)
            return fallback if (math.isnan(f) or math.isinf(f)) else f
        except (TypeError, ValueError):
            return fallback

    entry_default = _safe_float(entry_default, 100.0)
    stop_default = _safe_float(stop_default, entry_default * 0.95)
    target1_default = _safe_float(target1_default, entry_default * 1.10)
    cmp = _safe_float(cmp if cmp is not None else entry_default, entry_default)

    # ── Header ──────────────────────────────────────────
    col_h1, col_h2 = st.columns([2, 1])
    with col_h1:
        signal_badge = badge("BUY", "buy") if score >= 80 else badge("WATCH", "watch")
        st.markdown(
            f"<h2 style='margin:0'>{symbol} {signal_badge}</h2>"
            f"<p style='color:#8b949e;font-size:0.82rem;margin:4px 0 0'>"
            f"Setup: <b style='color:#e6edf3'>{setup}</b> &nbsp;|&nbsp; "
            f"Score: <b style='color:#e6edf3'>{score}/100</b> &nbsp;|&nbsp; "
            f"CMP: <b style='color:#00d4aa'>₹{cmp:,.2f}</b></p>",
            unsafe_allow_html=True,
        )
    with col_h2:
        st.link_button(
            "📊 TradingView Chart",
            make_tradingview_url(symbol),
            use_container_width=True,
        )

    st.divider()

    # ── Price inputs ─────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        entry = st.number_input("Entry Price (₹)", 0.05, value=round(entry_default, 2), step=0.5, key=f"{key_prefix}_entry")
    with c2:
        stop = st.number_input("Stop Loss (₹)", 0.01, value=round(stop_default, 2), step=0.5, key=f"{key_prefix}_stop")
    with c3:
        per_share_risk = max(entry - stop, 0.01) if entry > stop else 0.01
        auto_t1 = round(entry + 2 * per_share_risk, 2)
        target1 = st.number_input("Target 1 (₹) [2R]", 0.05, value=round(target1_default, 2), step=0.5, key=f"{key_prefix}_t1")
    with c4:
        auto_t2 = round(entry + 3 * per_share_risk, 2)
        target2 = st.number_input("Target 2 (₹) [3R]", 0.05, value=auto_t2, step=0.5, key=f"{key_prefix}_t2")

    # ── Validation warnings ───────────────────────────────
    if stop >= entry:
        st.warning("⚠️ Stop loss must be below entry price for a long trade.")
    if target1 <= entry:
        st.warning("⚠️ Target 1 must be above entry price.")

    # ── Capital / risk override ───────────────────────────
    with st.expander("⚙️ Adjust Capital & Risk", expanded=False):
        col_cap, col_risk = st.columns(2)
        with col_cap:
            t_cap = st.number_input("Trade Capital (₹)", 10_000, 10_000_000, int(capital), 5_000, key=f"{key_prefix}_cap")
        with col_risk:
            t_risk = st.slider("Risk per Trade (%)", 0.1, 2.0, float(risk_pct), 0.1, key=f"{key_prefix}_rpct")

    # ── Calculations ───────────────────────────────────────
    per_share_risk = max(entry - stop, 0.01) if (entry > stop) else 0.01
    risk_budget = (t_cap * t_risk / 100) if t_cap and t_risk else 0.0
    calc_qty = risk_budget / per_share_risk if per_share_risk > 0 else 0
    qty = max(0, int(calc_qty)) if not (math.isnan(calc_qty) or math.isinf(calc_qty)) else 0
    pos_val = qty * entry
    cap_pct = (pos_val / t_cap * 100) if t_cap > 0 else 0
    total_risk = qty * per_share_risk
    rr1 = ((target1 - entry) / per_share_risk) if per_share_risk > 0 else 0
    rr2 = ((target2 - entry) / per_share_risk) if per_share_risk > 0 else 0
    gain1 = qty * (target1 - entry)
    gain2 = qty * (target2 - entry)


    # ── Metrics ────────────────────────────────────────────
    st.markdown("##### 📊 Position Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Qty", f"{qty:,} shares")
    m2.metric("Position Value", f"₹{pos_val:,.0f}", f"{cap_pct:.1f}% deployed")
    m3.metric("Total Risk", f"₹{total_risk:,.0f}", f"-₹{per_share_risk:.2f}/share", delta_color="inverse")
    m4.metric("R:R at T1", f"1 : {rr1:.1f}R")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("T1 Profit", f"+₹{gain1:,.0f}", f"+{(target1/entry-1)*100:.1f}%")
    m6.metric("T2 Profit", f"+₹{gain2:,.0f}", f"+{(target2/entry-1)*100:.1f}%")
    m7.metric("R:R at T2", f"1 : {rr2:.1f}R")
    m8.metric("Max Loss", f"-₹{total_risk:,.0f}", f"{t_risk:.1f}% of capital", delta_color="inverse")

    # ── Order ticket ───────────────────────────────────────
    order_str = f"BUY {qty} {symbol} LIMIT ₹{entry:.2f}  |  SL ₹{stop:.2f}  |  T1 ₹{target1:.2f}  |  T2 ₹{target2:.2f}"
    st.code(order_str, language="text")
    st.caption("💡 Move SL to breakeven after T1 hit. Trail remaining half with 20 EMA.")

    # ── Add to Paper Book ──────────────────────────────────
    add_triggered = False
    if show_add_button and qty > 0:
        if st.button(f"📋 Add to Paper Book — {symbol}", type="primary", use_container_width=True, key=f"{key_prefix}_add"):
            trade_id = add_trade(symbol, setup, entry, stop, target1, target2, qty, t_cap)
            st.toast(f"✅ {symbol} added to Paper Book! Trade ID: {trade_id}", icon="📋")
            add_triggered = True

    return {
        "symbol": symbol,
        "entry": entry,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "qty": qty,
        "capital": t_cap,
        "risk_pct": t_risk,
        "add_triggered": add_triggered,
    }


# ---------------------------------------------------------------------------
# Equity curve chart
# ---------------------------------------------------------------------------

def plot_equity_curve(equity_df: pd.DataFrame, initial_capital: float = 100_000) -> None:
    """Plot an interactive equity curve using Plotly."""
    if equity_df.empty:
        st.info("No closed trades yet to build equity curve.")
        return

    fig = go.Figure()

    # Fill area
    fig.add_trace(go.Scatter(
        x=equity_df["exit_date"],
        y=equity_df["equity"],
        mode="lines",
        name="Portfolio Value",
        line=dict(color="#00d4aa", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(0,212,170,0.08)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>₹%{y:,.0f}<extra></extra>",
    ))

    # Baseline
    fig.add_hline(y=initial_capital, line_dash="dot", line_color="#30363d",
                  annotation_text="Starting Capital", annotation_font_color="#8b949e")

    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="Inter, system-ui", color="#e6edf3"),
        xaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False, title=""),
        yaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False, title="Portfolio ₹",
                   tickformat="₹,.0f"),
        margin=dict(l=10, r=10, t=20, b=10),
        height=320,
        showlegend=False,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_monthly_pnl(monthly_df: pd.DataFrame) -> None:
    """Bar chart of monthly net P&L."""
    if monthly_df.empty:
        st.info("No monthly data yet.")
        return

    colors = ["#00d4aa" if v >= 0 else "#ff4d6d" for v in monthly_df["Net PnL"]]

    fig = go.Figure(go.Bar(
        x=monthly_df["Month"],
        y=monthly_df["Net PnL"],
        marker_color=colors,
        hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="Inter, system-ui", color="#e6edf3"),
        xaxis=dict(gridcolor="#21262d", title=""),
        yaxis=dict(gridcolor="#21262d", title="Net P&L (₹)", tickformat="₹,.0f"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=260,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_backtest_equity(equity_series: pd.Series, initial_capital: float) -> None:
    """Equity curve chart for the backtest page."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_series.index,
        y=equity_series.values,
        mode="lines",
        line=dict(color="#388bfd", width=2),
        fill="tozeroy",
        fillcolor="rgba(56,139,253,0.07)",
        name="Equity",
        hovertemplate="<b>%{x|%b %Y}</b><br>₹%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=initial_capital, line_dash="dot", line_color="#30363d")
    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="Inter, system-ui", color="#e6edf3"),
        xaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False),
        yaxis=dict(gridcolor="#21262d", showgrid=True, zeroline=False, tickformat="₹,.0f"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        showlegend=False,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_trade_scatter(trades_df: pd.DataFrame) -> None:
    """Scatter of individual trade R-multiples for backtest page."""
    if trades_df.empty:
        return
    df = trades_df.copy()
    df["Color"] = df["PnL"].apply(lambda v: "#00d4aa" if v >= 0 else "#ff4d6d")
    df["Label"] = df["Reason"]

    fig = go.Figure(go.Scatter(
        x=list(range(1, len(df) + 1)),
        y=df["R"],
        mode="markers",
        marker=dict(color=df["Color"].tolist(), size=10, opacity=0.85),
        text=df["Label"],
        hovertemplate="Trade #%{x}<br>R: %{y:.2f}<br>%{text}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#30363d", line_dash="dash")
    fig.add_hline(y=1, line_color="#8b949e", line_dash="dot",
                  annotation_text="1R", annotation_font_color="#8b949e")
    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(family="Inter, system-ui", color="#e6edf3"),
        xaxis=dict(gridcolor="#21262d", title="Trade #"),
        yaxis=dict(gridcolor="#21262d", title="R-Multiple"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=260,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
