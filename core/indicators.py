"""
core/indicators.py
------------------
Pure-Python / Pandas indicator logic for Trend Momentum 4.
All functions are stateless and dependency-free (only numpy/pandas).
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Basic Indicators
# ---------------------------------------------------------------------------

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI using EWM (matches most trading platforms)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    prev = df["Close"].shift(1)
    tr = pd.concat(
        [df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich an OHLCV DataFrame with EMA20, EMA50, RSI14, RelVol, ATR14."""
    d = df.copy()
    d["EMA20"] = d["Close"].ewm(span=20, adjust=False).mean()
    d["EMA50"] = d["Close"].ewm(span=50, adjust=False).mean()
    d["RSI14"] = rsi(d["Close"], 14)
    d["AvgVol20"] = d["Volume"].rolling(20).mean()
    d["RelVol"] = d["Volume"] / d["AvgVol20"]
    d["Prev10High"] = d["High"].rolling(10).max().shift(1)
    d["ATR14"] = atr(d, 14)
    return d


# ---------------------------------------------------------------------------
# Weekly Filter
# ---------------------------------------------------------------------------

def weekly_filter(df: pd.DataFrame):
    """
    Returns (passes: bool, metrics: dict).
    Weekly trend: Close > EMA20 > EMA50, Weekly RSI > 55.
    Requires at least 70 daily bars (≈ 14 weeks).
    """
    if len(df) < 70:
        return False, {}
    w = df["Close"].resample("W-FRI").last().dropna()
    if len(w) < 60:
        return False, {}
    w20 = w.ewm(span=20, adjust=False).mean()
    w50 = w.ewm(span=50, adjust=False).mean()
    wrsi = rsi(w, 14)
    ok = bool(
        w.iloc[-1] > w20.iloc[-1]
        and w20.iloc[-1] > w50.iloc[-1]
        and wrsi.iloc[-1] > 55
    )
    return ok, {"Weekly RSI": float(wrsi.iloc[-1]), "Weekly Close": float(w.iloc[-1])}


# ---------------------------------------------------------------------------
# Signal Generator
# ---------------------------------------------------------------------------

def signal_for(
    ticker: str,
    df: pd.DataFrame,
    capital: float,
    risk_pct: float,
    min_relvol: float,
    rsi_threshold: float,
) -> dict | None:
    """
    Compute the trading signal for a single ticker.
    Returns a dict row or None if insufficient data.
    """
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

    setup = (
        "Breakout"
        if breakout and trend and momentum and volume
        else ("Trend" if trend and momentum and volume else "Watch")
    )

    # Stocks that don't fully qualify → returned as WATCH
    if not (wk_ok and trend and momentum and volume):
        return {
            "Symbol": ticker.replace(".NS", "").replace(".BO", ""),
            "Setup": setup,
            "Price": float(last["Close"]),
            "Weekly RSI": round(wk.get("Weekly RSI", np.nan), 1),
            "Daily RSI": round(float(last["RSI14"]), 1),
            "Rel Vol": round(float(last["RelVol"]), 2),
            "EMA20": round(float(last["EMA20"]), 2),
            "EMA50": round(float(last["EMA50"]), 2),
            "Entry": np.nan,
            "Stop": np.nan,
            "Target 1": np.nan,
            "Qty": 0,
            "Risk ₹": 0,
            "Score": 0,
            "Signal": "WATCH",
        }

    # Volatility-aware stop
    entry = float(last["Close"])
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
        "Symbol": ticker.replace(".NS", "").replace(".BO", ""),
        "Setup": setup,
        "Price": round(entry, 2),
        "Weekly RSI": round(wk.get("Weekly RSI", np.nan), 1),
        "Daily RSI": round(float(last["RSI14"]), 1),
        "Rel Vol": round(float(last["RelVol"]), 2),
        "EMA20": round(float(last["EMA20"]), 2),
        "EMA50": round(float(last["EMA50"]), 2),
        "Entry": round(entry, 2),
        "Stop": round(stop, 2),
        "Target 1": round(target1, 2),
        "Qty": qty,
        "Risk ₹": round(qty * risk_per_share, 2),
        "Score": score,
        "Signal": "BUY" if score >= 80 else "WATCH",
    }


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------

def backtest(
    df: pd.DataFrame,
    initial_capital: float,
    risk_pct: float,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[pd.DataFrame, dict]:
    """
    Bar-by-bar backtest on daily OHLCV data using the Trend Momentum rules.
    Returns (trades_df, stats_dict).
    """
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
            if row["Low"] <= stop:
                exit_price, reason = stop, "Stop"
            elif row["High"] >= target:
                exit_price, reason = target, "2R"
            else:
                equity.append((idx, cash + qty * row["Close"]))
                continue
            gross = (exit_price - entry) * qty
            costs = (entry + exit_price) * qty * (commission_bps + slippage_bps) / 10000
            pnl = gross - costs
            cash += pnl
            trades.append(
                {
                    "Entry Date": entry_date,
                    "Exit Date": idx,
                    "Entry": entry,
                    "Exit": exit_price,
                    "Qty": qty,
                    "PnL": pnl,
                    "R": pnl / max(risk_amt, 1),
                    "Reason": reason,
                }
            )
            in_trade = False
            qty = 0

        if not in_trade:
            trend = row["Close"] > row["EMA20"] > row["EMA50"]
            momentum = row["RSI14"] > 55
            volume = row["RelVol"] >= 1.5
            breakout = row["Close"] > row["Prev10High"]
            if trend and momentum and volume and breakout:
                rps = max(float(row["ATR14"] * 1.2), float(row["Close"] * 0.02))
                stop_candidate = float(row["Close"] - rps)
                if stop_candidate > 0:
                    qty = int(risk_amt / rps)
                    if qty > 0:
                        entry = float(row["Close"]) * (1 + slippage_bps / 10000)
                        stop = stop_candidate
                        target = entry + 2 * (entry - stop)
                        entry_date = idx
                        in_trade = True
        equity.append((idx, cash + (qty * row["Close"] if in_trade else 0)))

    eq = pd.DataFrame(equity, columns=["Date", "Equity"]).set_index("Date")
    t = pd.DataFrame(trades)

    empty_stats = {
        "final": cash,
        "return_pct": 0,
        "max_dd_pct": 0,
        "win_rate": 0,
        "profit_factor": 0,
        "trades": 0,
        "avg_R": 0,
    }
    if t.empty:
        return t, empty_stats

    wins = t[t["PnL"] > 0]["PnL"].sum()
    losses = -t[t["PnL"] < 0]["PnL"].sum()
    peak = eq["Equity"].cummax()
    dd = (eq["Equity"] / peak - 1) * 100
    stats = {
        "final": cash,
        "return_pct": (cash / initial_capital - 1) * 100,
        "max_dd_pct": float(dd.min()),
        "win_rate": float((t["PnL"] > 0).mean() * 100),
        "profit_factor": float(wins / losses) if losses > 0 else np.inf,
        "trades": len(t),
        "avg_R": float(t["R"].mean()),
        "equity": eq,
    }
    return t, stats
