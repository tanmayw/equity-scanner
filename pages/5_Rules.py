"""
pages/5_Rules.py  —  System Trading Rules
==========================================
The Trend Momentum 4 rule book presented as styled, readable cards.
"""

import streamlit as st

st.set_page_config(page_title="Rules · TrendMomentum", page_icon="📘", layout="wide")

from ui.styles import inject_css
from ui.components import render_sidebar

inject_css()
render_sidebar()

st.markdown(
    "<h1>📘 System Rules</h1>"
    "<p style='color:#8b949e;margin-top:-8px'>The complete Trend Momentum 4 rule book for entries, exits, and risk management.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Rule sections ─────────────────────────────────────────────────────────
rules = [
    {
        "icon": "🌍",
        "title": "1. Market Regime Filter",
        "color": "#388bfd",
        "rules": [
            "NIFTY 50 must be above its 20-week EMA and 20-week EMA above 50-week EMA.",
            "Weekly NIFTY RSI(14) must be above 55.",
            "No new longs if the broad market is in a confirmed downtrend.",
        ],
    },
    {
        "icon": "📅",
        "title": "2. Weekly Trend Filter",
        "color": "#00d4aa",
        "rules": [
            "Stock weekly Close > weekly EMA20 > weekly EMA50.",
            "Weekly RSI(14) > 55.",
            "Ensures you are with the higher-timeframe trend, not fighting it.",
        ],
    },
    {
        "icon": "📈",
        "title": "3. Daily Trend",
        "color": "#00d4aa",
        "rules": [
            "Daily Close > daily EMA20 > daily EMA50.",
            "Confirms short-term bullish alignment.",
        ],
    },
    {
        "icon": "⚡",
        "title": "4. Momentum",
        "color": "#f5a623",
        "rules": [
            "Daily RSI(14) > configured threshold (default 55).",
            "Avoids entering over-extended or exhausted moves.",
        ],
    },
    {
        "icon": "📊",
        "title": "5. Volume Confirmation",
        "color": "#f5a623",
        "rules": [
            "Relative volume (current / 20-day avg) ≥ configured threshold (default 1.5×).",
            "Ensures institutional participation and conviction behind the move.",
        ],
    },
    {
        "icon": "🚀",
        "title": "6. Preferred Entry — Breakout",
        "color": "#00d4aa",
        "rules": [
            "Close above the previous 10-day high (10-bar breakout).",
            "Use a limit order near the close or next day's open for breakout stocks.",
            "Trend-only setups (no breakout) score lower and carry more risk.",
        ],
    },
    {
        "icon": "🛑",
        "title": "7. Stop Loss",
        "color": "#ff4d6d",
        "rules": [
            "Initial stop = min(entry − 1.2 × ATR14, recent 5-bar swing low).",
            "Stop must be below entry at all times — no exceptions.",
            "Never move the stop further away from entry.",
        ],
    },
    {
        "icon": "🎯",
        "title": "8. Targets & Trail",
        "color": "#00d4aa",
        "rules": [
            "Target 1 (T1) = minimum 2R extension from entry.",
            "Target 2 (T2) = minimum 3R extension from entry.",
            "Book 50% at T1. Move stop to breakeven.",
            "Trail remaining 50% with the 20-day EMA on daily chart.",
        ],
    },
    {
        "icon": "💰",
        "title": "9. Position Sizing",
        "color": "#388bfd",
        "rules": [
            "Risk per trade = default 0.5% of total portfolio capital.",
            "Quantity = risk amount ÷ risk per share.",
            "Never risk more than 1% of capital on any single trade.",
        ],
    },
    {
        "icon": "🔢",
        "title": "10. Portfolio Rules",
        "color": "#388bfd",
        "rules": [
            "Maximum 3 simultaneous open positions (configurable up to 5).",
            "Maximum total capital at risk = 1.5% at any time.",
            "Never average down into a losing position.",
            "If no valid setup exists — cash is a valid position.",
        ],
    },
    {
        "icon": "⚠️",
        "title": "Disclaimer",
        "color": "#f5a623",
        "rules": [
            "This tool is for educational and research purposes only.",
            "Backtest results are historical simulations — not guarantees of future performance.",
            "Data comes from Yahoo Finance via yfinance; may differ from exchange-grade feeds.",
            "Always validate signals with your own analysis before placing real orders.",
            "Not a SEBI-registered investment advisor. Not investment advice.",
        ],
    },
]


for rule in rules:
    st.markdown(
        f"""
        <div style="
            background:#161b22;
            border:1px solid #30363d;
            border-left:4px solid {rule['color']};
            border-radius:12px;
            padding:20px 24px;
            margin-bottom:16px;
        ">
            <h3 style="margin:0 0 12px;color:#e6edf3">{rule['icon']} {rule['title']}</h3>
            {''.join(
                f"<p style='color:#8b949e;margin:0 0 6px;font-size:0.88rem;line-height:1.6'>"
                f"<span style='color:{rule['color']};margin-right:8px'>›</span>{r}</p>"
                for r in rule['rules']
            )}
        </div>
        """,
        unsafe_allow_html=True,
    )
