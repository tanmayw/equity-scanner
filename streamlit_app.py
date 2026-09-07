
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import urllib.request

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

def fetch_history(ticker, period="2y", interval="1d"):
    x = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if x.empty:
        return pd.DataFrame()
    if isinstance(x.columns, pd.MultiIndex):
        x.columns = x.columns.get_level_values(0)
    x = x.rename(columns=str.title)
    needed = ["Open","High","Low","Close","Volume"]
    return x[[c for c in needed if c in x.columns]].dropna()

@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker, period="2y", interval="1d"):
    return fetch_history(ticker, period=period, interval=interval)

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
        "Risk ₹": round(qty * risk_per_share, 2),
        "Score": score,
        "Signal": "BUY" if score >= 80 else "WATCH"
    }

def make_tradingview_url(sym: str) -> str:
    clean = str(sym).strip().upper()
    if clean.endswith(".NS"):
        clean = clean[:-3]
    elif clean.endswith(".BO"):
        bse_sym = clean[:-3]
        return f"https://in.tradingview.com/chart/?symbol=BSE:{bse_sym}#{clean}"
    tv_ticker = clean.replace("&", "_")
    return f"https://in.tradingview.com/chart/?symbol=NSE:{tv_ticker}#{clean}"

def render_trade_planner_widget(stock_row, capital, risk_pct, key_prefix="widget"):
    sym = stock_row.get("Symbol", "STOCK")
    entry_default = float(stock_row.get("Entry", stock_row.get("Price", 100.0)))
    stop_default = float(stock_row.get("Stop", entry_default * 0.95))
    target_default = float(stock_row.get("Target 1", entry_default + 2 * max(0.01, entry_default - stop_default)))
    setup_name = stock_row.get("Setup", "Trend")
    score_val = stock_row.get("Score", 80)
    cur_price = stock_row.get("Price", entry_default)

    with st.container(border=True):
        st.markdown(f"### 🧮 Trade Planner: **{sym}**")
        st.caption(f"Setup: **{setup_name}** | Momentum Score: **{score_val}/100** | CMP: **₹{cur_price:,.2f}**")

        st.link_button(
            f"📈 Open {sym} Chart on TradingView",
            make_tradingview_url(sym),
            use_container_width=True
        )

        st.markdown("---")

        c1, c2 = st.columns(2)
        with c1:
            entry = st.number_input(
                "Entry Price (₹)",
                min_value=0.05,
                value=round(entry_default, 2),
                step=0.5,
                key=f"{key_prefix}_entry"
            )
        with c2:
            stop = st.number_input(
                "Stop Loss (₹)",
                min_value=0.01,
                value=round(stop_default, 2),
                step=0.5,
                key=f"{key_prefix}_stop"
            )

        if stop >= entry:
            st.warning("⚠️ Stop loss should be below entry price for a long setup.")

        per_share_risk = max(entry - stop, 0.01)
        risk_2r_tgt = entry + 2 * per_share_risk
        risk_3r_tgt = entry + 3 * per_share_risk

        c3, c4 = st.columns(2)
        with c3:
            target1 = st.number_input(
                "Target 1 (₹)",
                min_value=0.05,
                value=round(target_default, 2),
                step=0.5,
                key=f"{key_prefix}_tgt1"
            )
        with c4:
            target2 = st.number_input(
                "Target 2 (₹) [3R Extension]",
                min_value=0.05,
                value=round(risk_3r_tgt, 2),
                step=0.5,
                key=f"{key_prefix}_tgt2"
            )

        if target1 <= entry:
            st.warning("⚠️ Target 1 should be above entry price for a long setup.")

        with st.expander("⚙️ Adjust Capital & Risk for this trade", expanded=False):
            t_cap = st.number_input("Trade Capital (₹)", 10000, 10000000, int(capital), 5000, key=f"{key_prefix}_cap")
            t_risk_pct = st.slider("Risk per trade (%)", 0.1, 2.0, float(risk_pct), 0.1, key=f"{key_prefix}_riskpct")

        risk_budget = t_cap * t_risk_pct / 100
        qty = max(0, int(risk_budget / per_share_risk)) if per_share_risk > 0 else 0
        pos_val = qty * entry
        cap_deployed_pct = (pos_val / t_cap * 100) if t_cap > 0 else 0
        total_risk = qty * per_share_risk
        rr1 = (target1 - entry) / per_share_risk if per_share_risk > 0 else 0
        gain1 = qty * (target1 - entry)
        gain2 = qty * (target2 - entry)

        st.markdown("##### Sizing & Metrics")
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Recommended Qty", f"{qty} shares")
        m_col2.metric("Position Capital", f"₹{pos_val:,.2f}", f"{cap_deployed_pct:.1f}% deployed")

        m_col3, m_col4 = st.columns(2)
        m_col3.metric("Total Risk", f"₹{total_risk:,.2f}", f"-₹{per_share_risk:,.2f} / share")
        m_col4.metric("Reward : Risk (T1)", f"1 : {rr1:.2f}")

        m_col5, m_col6 = st.columns(2)
        m_col5.metric("Target 1 Profit", f"+₹{gain1:,.2f}", f"+{(target1/entry - 1)*100:.1f}%")
        m_col6.metric("Target 2 Profit", f"+₹{gain2:,.2f}", f"+{(target2/entry - 1)*100:.1f}%")

        order_code = f"BUY {qty} {sym} LIMIT ₹{entry:.2f} | SL: ₹{stop:.2f} | T1: ₹{target1:.2f}"
        st.code(order_code, language="text")
        st.caption("💡 Move SL to breakeven after Target 1 is hit; trail remaining half with 20 EMA.")

NSE_INDEX_URLS = {
    "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "Nifty Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
    "Nifty Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
    "Nifty Midcap 150": "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
}

NIFTY50_FALLBACK = [
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","BHARTIARTL.NS",
"ITC.NS","SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","M&M.NS","BAJFINANCE.NS",
"MARUTI.NS","HINDUNILVR.NS","SUNPHARMA.NS","HCLTECH.NS","TITAN.NS","NTPC.NS",
"ADANIENT.NS","ADANIPORTS.NS","TATASTEEL.NS","POWERGRID.NS","ONGC.NS","COALINDIA.NS",
"ULTRACEMCO.NS","WIPRO.NS","NESTLEIND.NS","ASIANPAINT.NS","TECHM.NS","JSWSTEEL.NS",
"BAJAJFINSV.NS","TRENT.NS","BEL.NS","INDUSINDBK.NS","GRASIM.NS","CIPLA.NS","DRREDDY.NS",
"EICHERMOT.NS","HEROMOTOCO.NS","HINDALCO.NS","TATACONSUM.NS","BRITANNIA.NS","APOLLOHOSP.NS",
"SHRIRAMFIN.NS","BAJAJ-AUTO.NS","TATAMOTORS.NS","JIOFIN.NS","MAXHEALTH.NS"
]

@st.cache_data(ttl=86400, show_spinner=False)
def get_universe_tickers(universe_name):
    # 1. Fetch live index constituent CSV from NSE archives
    if universe_name in NSE_INDEX_URLS:
        try:
            url = NSE_INDEX_URLS[universe_name]
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                df = pd.read_csv(resp)
                if "Symbol" in df.columns:
                    symbols = [f"{s.strip().upper()}.NS" for s in df["Symbol"].dropna().unique() if s.strip()]
                    if len(symbols) >= 20:
                        return symbols
        except Exception:
            pass

    # 2. Check bundled local universes cache
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(base_dir, "data", "universes.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if universe_name in data and len(data[universe_name]) > 0:
                    return data[universe_name]
        except Exception:
            pass

    # 3. Built-in hardcoded fallback
    return NIFTY50_FALLBACK

def scan_single_stock(ticker, capital, risk_pct, min_relvol, rsi_threshold):
    try:
        df = fetch_history(ticker, "2y", "1d")
        return signal_for(ticker, df, capital, risk_pct, min_relvol, rsi_threshold)
    except Exception:
        return None

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
    st.subheader("Momentum Scanner")

    u_col1, u_col2 = st.columns([2, 1])
    with u_col1:
        universe_choice = st.selectbox(
            "Select Universe / Index",
            ["Nifty 50", "Nifty Next 50", "Nifty Midcap 100", "Nifty Midcap 150", "Nifty 500", "Custom Watchlist"],
            index=0,
            help="Choose an index to scan. For example, UNIONBANK.NS is in Nifty Next 50 and Nifty 500."
        )

    if universe_choice == "Custom Watchlist":
        custom_input = st.text_area(
            "Enter NSE symbols (comma or space separated)",
            value="UNIONBANK.NS, TATAPOWER.NS, SBIN.NS, IRFC.NS, BEL.NS",
            help="You can enter tickers with or without .NS (e.g. UNIONBANK, TCS)"
        )
        raw_symbols = [s.strip().upper() for s in custom_input.replace("\n", ",").split(",") if s.strip()]
        target_tickers = [s if (s.endswith(".NS") or s.endswith(".BO")) else f"{s}.NS" for s in raw_symbols]
    else:
        target_tickers = get_universe_tickers(universe_choice)

    with u_col2:
        st.metric("Universe Size", f"{len(target_tickers)} stocks")

    scan_btn_label = f"🔄 Run scanner on {universe_choice}"
    if st.button(scan_btn_label, type="primary"):
        rows = []
        progress = st.progress(0)
        status_text = st.empty()
        total = len(target_tickers)
        completed = 0

        # Run concurrent downloads and scans across worker pool
        max_workers = min(15, max(4, len(target_tickers) // 10))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(scan_single_stock, ticker, capital, risk_pct, min_relvol, rsi_threshold): ticker
                for ticker in target_tickers
            }
            for future in as_completed(future_to_ticker):
                completed += 1
                res = future.result()
                if res:
                    rows.append(res)
                progress.progress(completed / total)
                status_text.caption(f"Scanning {completed}/{total} stocks... ({int(completed/total*100)}%)")

        status_text.empty()
        out = pd.DataFrame(rows)
        if not out.empty:
            out = out.sort_values(["Signal","Score","Daily RSI"], ascending=[True,False,False])
            st.session_state["scan"] = out
            st.session_state["scanned_universe"] = f"{universe_choice} ({len(target_tickers)} stocks)"

    if "scan" in st.session_state:
        out = st.session_state["scan"]
        buys = out[out["Signal"]=="BUY"]
        scanned_info = st.session_state.get("scanned_universe", "")

        m1, m2, m3 = st.columns(3)
        m1.metric("BUY Setups", len(buys))
        m2.metric("Watchlist Candidates", len(out) - len(buys))
        if scanned_info:
            m3.metric("Scanned Universe", scanned_info)

        filter_sym = st.text_input("🔍 Quick search / filter symbol (e.g. UNIONBANK, TATA):", "").strip().upper()
        filtered_out = out[out["Symbol"].str.contains(filter_sym, na=False)] if filter_sym else out
        filtered_buys = filtered_out[filtered_out["Signal"]=="BUY"]

        st.markdown("### Qualifying BUY Setups")
        if filtered_buys.empty:
            if buys.empty:
                st.info("No qualifying BUY setups found. Cash is a valid position.")
            else:
                st.info(f"No BUY setups matching search '{filter_sym}'.")
        else:
            # Store list of clean symbols for state lookup and callbacks
            clean_buy_symbols = filtered_buys["Symbol"].tolist()
            st.session_state["active_buy_symbols_list"] = clean_buy_symbols

            # Ensure selected_buy_symbol is valid
            if "selected_buy_symbol" not in st.session_state or st.session_state["selected_buy_symbol"] not in clean_buy_symbols:
                st.session_state["selected_buy_symbol"] = clean_buy_symbols[0]

            # Callback when user clicks the "Plan" button in the dataframe
            def handle_buy_plan_click():
                click_info = st.session_state.get("buy_plan_btn")
                if click_info is not None:
                    row_idx = getattr(click_info, "row", None)
                    if row_idx is None and isinstance(click_info, dict):
                        row_idx = click_info.get("row")
                    syms = st.session_state.get("active_buy_symbols_list", [])
                    if row_idx is not None and 0 <= row_idx < len(syms):
                        chosen = syms[row_idx]
                        st.session_state["selected_buy_symbol"] = chosen
                        st.session_state["planner_dropdown_selector"] = chosen

            # Also provide quick pill buttons right above for effortless 1-click switching
            current_active = st.session_state["selected_buy_symbol"]
            curr_pill_idx = clean_buy_symbols.index(current_active) if current_active in clean_buy_symbols else 0

            pills_selection = st.pills(
                "⚡ Quick Stock Selector for Trade Planner:",
                clean_buy_symbols,
                default=clean_buy_symbols[curr_pill_idx],
                key="buy_stock_pills"
            )
            if pills_selection and pills_selection != st.session_state["selected_buy_symbol"]:
                st.session_state["selected_buy_symbol"] = pills_selection
                st.session_state["planner_dropdown_selector"] = pills_selection
                st.rerun()

            col_grid, col_planner = st.columns([1.55, 1.0], gap="medium")

            # Prepare display dataframe with clickable TradingView links and Plan button
            display_buys = filtered_buys.copy()
            display_buys["Symbol"] = display_buys["Symbol"].apply(make_tradingview_url)
            display_buys.insert(1, "Plan", "🧮 Plan")

            with col_grid:
                grid_config = {
                    "Symbol": st.column_config.LinkColumn(
                        "Symbol",
                        help="Click to open TradingView interactive chart in new tab",
                        display_text=r"#(.*)",
                        pinned=True
                    ),
                    "Plan": st.column_config.ButtonColumn(
                        "Plan",
                        help="Click to load into the Trade Planner widget",
                        on_click=handle_buy_plan_click,
                        key="buy_plan_btn",
                        width="small"
                    )
                }

                buy_event = st.dataframe(
                    display_buys,
                    use_container_width=True,
                    hide_index=True,
                    column_config=grid_config,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="buy_grid_table"
                )

                # If user selected a row in the table, sync to active symbol
                if buy_event and hasattr(buy_event, "selection") and buy_event.selection and buy_event.selection.rows:
                    sel_row = buy_event.selection.rows[0]
                    if 0 <= sel_row < len(clean_buy_symbols):
                        new_sym = clean_buy_symbols[sel_row]
                        if new_sym != st.session_state.get("selected_buy_symbol"):
                            st.session_state["selected_buy_symbol"] = new_sym
                            st.session_state["planner_dropdown_selector"] = new_sym
                            st.rerun()

            with col_planner:
                def on_dropdown_select():
                    new_sym = st.session_state.get("planner_dropdown_selector")
                    if new_sym and new_sym in clean_buy_symbols:
                        st.session_state["selected_buy_symbol"] = new_sym

                # Keep dropdown synced with selected_buy_symbol
                active_sym = st.session_state.get("selected_buy_symbol", clean_buy_symbols[0])
                if active_sym not in clean_buy_symbols:
                    active_sym = clean_buy_symbols[0]
                    st.session_state["selected_buy_symbol"] = active_sym

                if "planner_dropdown_selector" not in st.session_state or st.session_state["planner_dropdown_selector"] != active_sym:
                    st.session_state["planner_dropdown_selector"] = active_sym

                st.selectbox(
                    "🎯 Plan Trade for Stock:",
                    clean_buy_symbols,
                    key="planner_dropdown_selector",
                    on_change=on_dropdown_select,
                    help="Select any BUY candidate or click any row / 🧮 Plan button in the table to plan trade"
                )

                stock_row = filtered_buys[filtered_buys["Symbol"] == active_sym].iloc[0]
                render_trade_planner_widget(
                    stock_row,
                    capital=capital,
                    risk_pct=risk_pct,
                    key_prefix=f"widget_{active_sym}"
                )

        with st.expander(f"All Scanned Candidates ({len(filtered_out)} displayed)"):
            display_all = filtered_out.copy()
            display_all["Symbol"] = display_all["Symbol"].apply(make_tradingview_url)
            st.dataframe(
                display_all,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Symbol": st.column_config.LinkColumn(
                        "Symbol",
                        help="Click to open TradingView interactive chart in new tab",
                        display_text=r"#(.*)",
                        pinned=True
                    )
                }
            )

        st.download_button("📥 Download scanner CSV", out.to_csv(index=False), "scanner.csv", "text/csv")

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

    scanned_buys = []
    if "scan" in st.session_state and not st.session_state["scan"].empty:
        scanned_buys = st.session_state["scan"][st.session_state["scan"]["Signal"] == "BUY"]["Symbol"].tolist()

    if scanned_buys:
        selected_to_load = st.selectbox(
            "Load setup from scanner:",
            ["-- Custom / Manual Entry --"] + scanned_buys,
            key="tab2_stock_loader"
        )
        if selected_to_load != "-- Custom / Manual Entry --":
            loaded_row = st.session_state["scan"][st.session_state["scan"]["Symbol"] == selected_to_load].iloc[0]
            render_trade_planner_widget(loaded_row, capital, risk_pct, key_prefix="tab2_loaded")
        else:
            entry = st.number_input("Entry price", min_value=0.05, value=1000.0, step=1.0, key="tab2_manual_entry")
            stop = st.number_input("Stop price", min_value=0.01, value=980.0, step=1.0, key="tab2_manual_stop")
            target = st.number_input("Target price", min_value=0.05, value=1040.0, step=1.0, key="tab2_manual_tgt")
            risk_rupees = capital * risk_pct / 100
            per_share = abs(entry-stop)
            qty = int(risk_rupees/per_share) if per_share > 0 else 0
            st.metric("Suggested quantity", qty)
            st.metric("Position value", f"₹{qty*entry:,.0f}")
            st.metric("Risk", f"₹{qty*per_share:,.0f}")
            rr = abs(target-entry)/per_share if per_share > 0 else 0
            st.metric("R:R", f"1 : {rr:.2f}")
    else:
        entry = st.number_input("Entry price", min_value=0.05, value=1000.0, step=1.0, key="tab2_manual_entry")
        stop = st.number_input("Stop price", min_value=0.01, value=980.0, step=1.0, key="tab2_manual_stop")
        target = st.number_input("Target price", min_value=0.05, value=1040.0, step=1.0, key="tab2_manual_tgt")
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
