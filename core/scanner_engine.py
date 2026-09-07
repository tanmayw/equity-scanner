"""
core/scanner_engine.py
-----------------------
Universe loading and parallel scan orchestration.
"""

import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st
import yfinance as yf

from core.indicators import signal_for

# ---------------------------------------------------------------------------
# Universe definitions
# ---------------------------------------------------------------------------

NSE_INDEX_URLS = {
    "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "Nifty Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
    "Nifty Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
    "Nifty Midcap 150": "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
}

NIFTY50_FALLBACK = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
    "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "AXISBANK.NS",
    "KOTAKBANK.NS", "M&M.NS", "BAJFINANCE.NS", "MARUTI.NS", "HINDUNILVR.NS",
    "SUNPHARMA.NS", "HCLTECH.NS", "TITAN.NS", "NTPC.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "TATASTEEL.NS", "POWERGRID.NS", "ONGC.NS", "COALINDIA.NS",
    "ULTRACEMCO.NS", "WIPRO.NS", "NESTLEIND.NS", "ASIANPAINT.NS", "TECHM.NS",
    "JSWSTEEL.NS", "BAJAJFINSV.NS", "TRENT.NS", "BEL.NS", "INDUSINDBK.NS",
    "GRASIM.NS", "CIPLA.NS", "DRREDDY.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "TATACONSUM.NS", "BRITANNIA.NS", "APOLLOHOSP.NS",
    "SHRIRAMFIN.NS", "BAJAJ-AUTO.NS", "TATAMOTORS.NS", "JIOFIN.NS", "MAXHEALTH.NS",
]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_history(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    x = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if x.empty:
        return pd.DataFrame()
    if isinstance(x.columns, pd.MultiIndex):
        x.columns = x.columns.get_level_values(0)
    x = x.rename(columns=str.title)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    return x[[c for c in needed if c in x.columns]].dropna()


@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    return fetch_history(ticker, period=period, interval=interval)


# ---------------------------------------------------------------------------
# Universe loader
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def get_universe_tickers(universe_name: str) -> list[str]:
    """Load tickers for a named universe. Falls back gracefully."""
    # 1. Try live NSE CSV
    if universe_name in NSE_INDEX_URLS:
        try:
            url = NSE_INDEX_URLS[universe_name]
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                df = pd.read_csv(resp)
                if "Symbol" in df.columns:
                    symbols = [
                        f"{s.strip().upper()}.NS"
                        for s in df["Symbol"].dropna().unique()
                        if s.strip()
                    ]
                    if len(symbols) >= 20:
                        return symbols
        except Exception:
            pass

    # 2. Try local universes.json
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_path = os.path.join(base_dir, "data", "universes.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if universe_name in data and len(data[universe_name]) > 0:
                    return data[universe_name]
        except Exception:
            pass

    return NIFTY50_FALLBACK


@st.cache_data(ttl=900, show_spinner=False)
def get_benchmark_history(ticker: str = "^NSEI", period: str = "2y") -> pd.Series:
    """Fetch Nifty 50 benchmark Close prices for relative strength calculation."""
    try:
        df = fetch_history(ticker, period=period)
        if not df.empty and "Close" in df.columns:
            return df["Close"]
    except Exception:
        pass
    return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# Scan executor
# ---------------------------------------------------------------------------

def scan_single_stock(ticker, capital, risk_pct, min_relvol, rsi_threshold, bench_series=None):
    try:
        df = fetch_history(ticker, "2y", "1d")
        return signal_for(ticker, df, capital, risk_pct, min_relvol, rsi_threshold, bench_series=bench_series)
    except Exception:
        return None


def run_scan(
    tickers: list[str],
    capital: float,
    risk_pct: float,
    min_relvol: float,
    rsi_threshold: float,
    progress_callback=None,
    bench_ticker: str = "^NSEI",
) -> pd.DataFrame:
    """
    Parallel scan of all tickers with Nifty 50 benchmark RS calculation.
    progress_callback(completed, total) for UI updates.
    Returns a sorted DataFrame of scan results.
    """
    rows = []
    total = len(tickers)
    completed = 0
    max_workers = min(15, max(4, total // 10))

    bench_series = get_benchmark_history(bench_ticker)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                scan_single_stock, ticker, capital, risk_pct, min_relvol, rsi_threshold, bench_series
            ): ticker
            for ticker in tickers
        }

        for future in as_completed(futures):
            completed += 1
            result = future.result()
            if result:
                rows.append(result)
            if progress_callback:
                progress_callback(completed, total)

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    return out.sort_values(
        ["Signal", "Score", "Daily RSI"], ascending=[True, False, False]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# TradingView URL builder
# ---------------------------------------------------------------------------

def make_tradingview_url(sym: str) -> str:
    clean = str(sym).strip().upper()
    if clean.endswith(".NS"):
        clean = clean[:-3]
    elif clean.endswith(".BO"):
        bse_sym = clean[:-3]
        return f"https://in.tradingview.com/chart/?symbol=BSE:{bse_sym}#{clean}"
    tv_ticker = clean.replace("&", "_")
    return f"https://in.tradingview.com/chart/?symbol=NSE:{tv_ticker}#{clean}"
