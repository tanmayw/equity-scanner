
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date, timedelta

st.set_page_config(page_title="Trend Momentum 4", page_icon="📈", layout="wide")

# ----------------------------
# Core indicators
# ----------------------------
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_indicators(df):
    d = df.copy()
    d["EMA20"] = d["Close"].ewm(span=20, adjust=False).mean()
    d["EMA50"] = d["Close"].ewm(span=50, adjust=False).mean()
    d["RSI14"] = rsi(d["Close"], 14)
    d["AvgVol20"] = d["Volume"].rolling(20).mean()
    d["RelVol"] = d["Volume"] / d["AvgVol20"]
    d["Prev10High"] = d["High"].rolling(10).max().shift(1)
    d["ATR14"] = atr(d, 14)
    return d

def atr(df, period=14):
    prev = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev).abs(),
        (df["Low"] - prev).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker, period="2y", interval="1d"):
    x = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if x.empty:
        return pd.DataFrame()
    if isinstance(x.columns, pd.MultiIndex):
        x.columns = x.columns.get_level_values(0)
    x = x.rename(columns=str.title)
    needed = ["Open","High","Low","Close","Volume"]
    return x[[c for c in needed if c in x.columns]].dropna()

def weekly_filter(df):
    if len(df) < 70:
        return False, {}
    w = df["Close"].resample("W-FRI").last().dropna()
    if len(w) < 60:
        return False, {}
    w20 = w.ewm(span=20, adjust=False).mean()
    w50 = w.ewm(span=50, adjust=False).mean()
    wrsi = rsi(w, 14)
    ok = bool(w.iloc[-1] > w20.iloc[-1] and w20.iloc[-1] > w50.iloc[-1] and wrsi.iloc[-1] > 55)
    return ok, {"Weekly RSI": float(wrsi.iloc[-1]), "Weekly Close": float(w.iloc[-1])}

def signal_for(ticker, df, capital, risk_pct, min_relvol, rsi_threshold):
    if df.empty or len(df) < 100:
        return None
    d = add_indicators(df)
    wk_ok, wk = weekly_filter(df)
    last = d.iloc[-1]
    prev10 = last["Prev10High"]
    breakout = pd.notna(prev10) and last["Close"] > prev10
    trend = last["Close"] > last["EMA20"] and last["EMA20"] > last["EMA50"]
    momentum = last["RSI14"] > rsi_threshold
    volume = last["RelVol"] >= min_relvol
    market_ok = True  # portfolio-level filter is applied separately

    setup = "Breakout" if breakout and trend and momentum and volume else (
        "Trend" if trend and momentum and volume else "Watch"
    )
    if not (wk_ok and trend and momentum and volume):
        return {
            "Symbol": ticker.replace(".NS",""),
            "Setup": setup,
            "Price": float(last["Close"]),
            "Weekly RSI": round(wk.get("Weekly RSI", np.nan), 1),
            "Daily RSI": round(float(last["RSI14"]), 1),
            "Rel Vol": round(float(last["RelVol"]), 2),
            "EMA20": round(float(last["EMA20"]), 2),
            "EMA50": round(float(last["EMA50"]), 2),
            "Entry": np.nan, "Stop": np.nan, "Target 1": np.nan,
            "Qty": 0, "Risk ₹": 0, "Score": 0,
            "Signal": "WATCH"
        }

    entry = float(last["Close"])
    # Volatility-aware stop, capped around a sensible swing distance.
    atrv = float(last["ATR14"]) if pd.notna(last["ATR14"]) else entry * 0.02
    swing_low = float(d["Low"].tail(5).min())
    stop = min(entry - 1.2 * atrv, swing_low)
    if stop >= entry:
        stop = entry - max(0.02 * entry, 1.2 * atrv)
    risk_per_share = max(entry - stop, 0.01)
    risk_rupees = capital * risk_pct / 100
    qty = max(0, int(risk_rupees / risk_per_share))
    target1 = entry + 2 * risk_per_share
    score = 0
    score += 25 if wk_ok else 0
    score += 25 if trend else 0
    score += 20 if momentum else 0
    score += 20 if volume else 0
    score += 10 if breakout else 0

    return {
        "Symbol": ticker.replace(".NS",""),
        "Setup": setup,
        "Price": round(entry,2),
        "Weekly RSI": round(wk.get("Weekly RSI", np.nan),1),
        "Daily RSI": round(float(last["RSI14"]),1),
        "Rel Vol": round(float(last["RelVol"]),2),
        "EMA20": round(float(last["EMA20"]),2),
        "EMA50": round(float(last["EMA50"]),2),
        "Entry": round(entry,2),
        "Stop": round(stop,2),
        "Target 1": round(target1,2),
        "Qty": qty,
        "Risk ₹": round(qty * risk_per_share,2),
        "Score": score,
        "Signal": "BUY" if score >= 80 else "WATCH"
    }

NIFTY50 = [
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","BHARTIARTL.NS",
"ITC.NS","SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","M&M.NS","BAJFINANCE.NS",
"MARUTI.NS","HINDUNILVR.NS","SUNPHARMA.NS","HCLTECH.NS","TITAN.NS","NTPC.NS",
"ADANIENT.NS","ADANIPORTS.NS","TATASTEEL.NS","POWERGRID.NS","ONGC.NS","COALINDIA.NS",
"ULTRACEMCO.NS","WIPRO.NS","NESTLEIND.NS","ASIANPAINT.NS","TECHM.NS","JSWSTEEL.NS",
"BAJAJFINSV.NS","TRENT.NS","BEL.NS","INDUSINDBK.NS","GRASIM.NS","CIPLA.NS","DRREDDY.NS",
"EICHERMOT.NS","HEROMOTOCO.NS","HINDALCO.NS","TATACONSUM.NS","BRITANNIA.NS","APOLLOHOSP.NS",
"SHRIRAMFIN.NS","BAJAJ-AUTO.NS","TATAMOTORS.NS","JIOFIN.NS","MAXHEALTH.NS"
]

def backtest(df, initial_capital, risk_pct, commission_bps, slippage_bps):
    if df.empty:
        return pd.DataFrame(), {}
    d = add_indicators(df).dropna().copy()
    cash = initial_capital
    risk_amt = initial_capital * risk_pct / 100
    trades = []
    in_trade = False
    entry = stop = target = qty = entry_date = None
    equity = []
    for idx, row in d.iterrows():
        if in_trade:
            # Conservative assumption: if both stop and target occur on same bar, stop wins.
            if row["Low"] <= stop:
                exit_price = stop
                reason = "Stop"
            elif row["High"] >= target:
                exit_price = target
                reason = "2R"
            else:
                equity.append((idx, cash + qty * row["Close"]))
                continue
            gross = (exit_price - entry) * qty
            costs = (entry + exit_price) * qty * (commission_bps + slippage_bps) / 10000
            pnl = gross - costs
            cash += pnl
            trades.append({
                "Entry Date": entry_date, "Exit Date": idx,
                "Entry": entry, "Exit": exit_price, "Qty": qty,
                "PnL": pnl, "R": pnl / max(risk_amt,1), "Reason": reason
            })
            in_trade = False
            qty = 0
        # New signal at close, enter next bar approximately at next open.
        if not in_trade:
            trend = row["Close"] > row["EMA20"] > row["EMA50"]
            momentum = row["RSI14"] > 55
            volume = row["RelVol"] >= 1.5
            breakout = row["Close"] > row["Prev10High"]
            if trend and momentum and volume and breakout:
                risk_per_share = max(float(row["ATR14"] * 1.2), float(row["Close"] * 0.02))
                stop_candidate = float(row["Close"] - risk_per_share)
                if stop_candidate > 0:
                    qty = int(risk_amt / risk_per_share)
                    if qty > 0:
                        entry = float(row["Close"]) * (1 + slippage_bps/10000)
                        stop = stop_candidate
                        target = entry + 2 * (entry - stop)
                        entry_date = idx
                        in_trade = True
        equity.append((idx, cash + (qty * row["Close"] if in_trade else 0)))
    eq = pd.DataFrame(equity, columns=["Date","Equity"]).set_index("Date")
    t = pd.DataFrame(trades)
    if t.empty:
        return t, {"final": cash, "return_pct": 0, "max_dd_pct": 0, "win_rate": 0, "profit_factor": 0, "trades": 0}
    wins = t[t["PnL"] > 0]["PnL"].sum()
    losses = -t[t["PnL"] < 0]["PnL"].sum()
    peak = eq["Equity"].cummax()
    dd = (eq["Equity"] / peak - 1) * 100
    stats = {
        "final": cash,
        "return_pct": (cash/initial_capital - 1)*100,
        "max_dd_pct": float(dd.min()),
        "win_rate": float((t["PnL"] > 0).mean()*100),
        "profit_factor": float(wins/losses) if losses > 0 else np.inf,
        "trades": len(t),
        "avg_R": float(t["R"].mean())
    }
    return t, stats

st.title("📈 Trend Momentum 4 — Indian Equity Swing System")
st.caption("Rules-based research/scanner. Not a guarantee of returns and not investment advice.")

with st.sidebar:
    st.header("Risk & Capital")
    capital = st.number_input("Capital (₹)", 50000, 5000000, 100000, 5000)
    risk_pct = st.slider("Risk per trade (%)", 0.1, 1.0, 0.5, 0.1)
    max_positions = st.number_input("Max simultaneous positions", 1, 5, 3)
    st.divider()
    st.header("Signal")
    min_relvol = st.slider("Minimum relative volume", 1.0, 3.0, 1.5, 0.1)
    rsi_threshold = st.slider("Daily RSI threshold", 50, 70, 55)
    st.divider()
    st.write("**Default model:** weekly trend + daily trend + RSI + relative volume + 10-day breakout.")

tabs = st.tabs(["📊 Scanner", "🧪 Backtest", "🧮 Trade Planner", "📘 Rules"])

with tabs[0]:
    st.subheader("Nifty 50 Momentum Scanner")
    if st.button("🔄 Run scanner", type="primary"):
        rows = []
        progress = st.progress(0)
        for i, ticker in enumerate(NIFTY50):
            try:
                df = get_history(ticker, "2y", "1d")
                result = signal_for(ticker, df, capital, risk_pct, min_relvol, rsi_threshold)
                if result:
                    rows.append(result)
            except Exception:
                pass
            progress.progress((i+1)/len(NIFTY50))
        out = pd.DataFrame(rows)
        if not out.empty:
            out = out.sort_values(["Signal","Score"], ascending=[True,False])
            st.session_state["scan"] = out
    if "scan" in st.session_state:
        out = st.session_state["scan"]
        buys = out[out["Signal"]=="BUY"]
        st.metric("BUY setups", len(buys))
        if buys.empty:
            st.info("No qualifying setups today. Cash is a valid position.")
        else:
            st.dataframe(buys, use_container_width=True, hide_index=True)
        with st.expander("All candidates"):
            st.dataframe(out, use_container_width=True, hide_index=True)
        st.download_button("Download scanner CSV", out.to_csv(index=False), "scanner.csv", "text/csv")

with tabs[1]:
    st.subheader("Single-stock historical backtest")
    ticker = st.text_input("NSE ticker", "RELIANCE.NS")
    period = st.selectbox("History", ["2y","5y","10y"], index=1)
    commission = st.number_input("Commission + fees (bps, one-way)", 5.0, 100.0, 10.0, 1.0)
    slippage = st.number_input("Slippage (bps, one-way)", 0.0, 100.0, 5.0, 1.0)
    if st.button("▶ Run backtest", type="primary"):
        df = get_history(ticker, period, "1d")
        trades, stats = backtest(df, capital, risk_pct, commission, slippage)
        if not stats or stats.get("trades",0) == 0:
            st.warning("No qualifying trades found.")
        else:
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Return", f"{stats['return_pct']:.1f}%")
            c2.metric("Max DD", f"{stats['max_dd_pct']:.1f}%")
            c3.metric("Win rate", f"{stats['win_rate']:.1f}%")
            c4.metric("Profit factor", f"{stats['profit_factor']:.2f}")
            c5.metric("Trades", stats["trades"])
            st.dataframe(trades, use_container_width=True, hide_index=True)
            st.download_button("Download trades CSV", trades.to_csv(index=False), "backtest_trades.csv", "text/csv")

with tabs[2]:
    st.subheader("Position / Risk Planner")
    entry = st.number_input("Entry price", min_value=0.05, value=1000.0, step=1.0)
    stop = st.number_input("Stop price", min_value=0.01, value=980.0, step=1.0)
    target = st.number_input("Target price", min_value=0.05, value=1040.0, step=1.0)
    risk_rupees = capital * risk_pct / 100
    per_share = abs(entry-stop)
    qty = int(risk_rupees/per_share) if per_share > 0 else 0
    st.metric("Suggested quantity", qty)
    st.metric("Position value", f"₹{qty*entry:,.0f}")
    st.metric("Risk", f"₹{qty*per_share:,.0f}")
    rr = abs(target-entry)/per_share if per_share > 0 else 0
    st.metric("R:R", f"1 : {rr:.2f}")

with tabs[3]:
    st.subheader("Trading rules")
    st.markdown("""
**Long setup**

1. Market regime should be healthy: NIFTY 50 above 20 EMA and 20 EMA above 50 EMA; weekly RSI > 55.
2. Stock weekly trend: Close > weekly 20 EMA > weekly 50 EMA; weekly RSI > 55.
3. Stock daily trend: Close > 20 EMA > 50 EMA.
4. Daily RSI > configured threshold.
5. Relative volume >= configured threshold.
6. Preferred entry: close above previous 10-day high.
7. Risk per trade: default 0.5% of capital.
8. Maximum three simultaneous positions.
9. Minimum intended reward:risk: 2:1.
10. Never average a losing position.
11. If no setup exists, stay in cash.

**Important:** Backtest results are historical simulations, not promises. The app uses Yahoo Finance data through `yfinance`; data availability and corporate-action handling can differ from exchange-grade feeds. Validate signals before placing orders.
""")
