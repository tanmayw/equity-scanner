"""
core/paper_book.py
------------------
Paper Trading Journal CRUD operations.
All trades persisted in data/paper_trades.json for cross-session durability.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime

import pandas as pd


# ---------------------------------------------------------------------------
# Storage path
# ---------------------------------------------------------------------------

def _journal_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", "paper_trades.json")


# ---------------------------------------------------------------------------
# Low-level I/O
# ---------------------------------------------------------------------------

def _load_raw() -> list[dict]:
    path = _journal_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_raw(trades: list[dict]) -> None:
    path = _journal_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_trades() -> pd.DataFrame:
    """Return all paper trades as a DataFrame."""
    raw = _load_raw()
    if not raw:
        return _empty_df()
    df = pd.DataFrame(raw)
    # Ensure all expected columns exist
    for col in _schema_columns():
        if col not in df.columns:
            df[col] = None
    return df[_schema_columns()]


def add_trade(
    symbol: str,
    setup: str,
    entry: float,
    stop: float,
    target1: float,
    target2: float,
    qty: int,
    capital: float,
    notes: str = "",
) -> str:
    """Persist a new OPEN paper trade. Returns the new trade_id."""
    trade_id = str(uuid.uuid4())[:8].upper()
    record = {
        "trade_id": trade_id,
        "symbol": symbol.upper(),
        "setup": setup,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "qty": int(qty),
        "capital_used": round(qty * entry, 2),
        "risk_per_share": round(entry - stop, 2),
        "total_risk": round(qty * max(entry - stop, 0.01), 2),
        "entry_date": date.today().isoformat(),
        "exit_price": None,
        "exit_date": None,
        "exit_reason": None,
        "pnl": None,
        "pnl_pct": None,
        "r_multiple": None,
        "notes": notes,
        "status": "OPEN",
    }
    trades = _load_raw()
    trades.append(record)
    _save_raw(trades)
    return trade_id


def close_trade(
    trade_id: str,
    exit_price: float,
    exit_reason: str,
    exit_date: str | None = None,
    notes: str | None = None,
) -> bool:
    """
    Close an open paper trade.
    exit_reason: one of 'Target 1', 'Target 2', 'Stop Loss', 'Manual'
    Returns True if found and updated.
    """
    trades = _load_raw()
    for t in trades:
        if t["trade_id"] == trade_id and t["status"] == "OPEN":
            qty = t["qty"]
            entry = t["entry"]
            stop = t["stop"]
            risk_ps = max(entry - stop, 0.01)

            pnl = (exit_price - entry) * qty
            pnl_pct = (exit_price / entry - 1) * 100
            r_multiple = pnl / max(qty * risk_ps, 0.01)

            t["exit_price"] = round(exit_price, 2)
            t["exit_date"] = exit_date or date.today().isoformat()
            t["exit_reason"] = exit_reason
            t["pnl"] = round(pnl, 2)
            t["pnl_pct"] = round(pnl_pct, 2)
            t["r_multiple"] = round(r_multiple, 2)
            t["status"] = "CLOSED"
            if notes is not None:
                t["notes"] = notes

            _save_raw(trades)
            return True
    return False


def update_trade(trade_id: str, **kwargs) -> bool:
    """Update arbitrary fields on an OPEN trade (e.g. stop, target1, notes)."""
    trades = _load_raw()
    for t in trades:
        if t["trade_id"] == trade_id:
            for k, v in kwargs.items():
                if k in t:
                    t[k] = v
            _save_raw(trades)
            return True
    return False


def delete_trade(trade_id: str) -> bool:
    """Permanently remove a trade record."""
    trades = _load_raw()
    new_trades = [t for t in trades if t["trade_id"] != trade_id]
    if len(new_trades) == len(trades):
        return False
    _save_raw(new_trades)
    return True


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def monthly_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per calendar month summarising closed trades.
    Columns: Month, Trades, Wins, Win%, Net PnL, Avg R, Best, Worst
    """
    closed = df[df["status"] == "CLOSED"].copy()
    if closed.empty:
        return pd.DataFrame()

    closed["exit_date"] = pd.to_datetime(closed["exit_date"])
    closed["Month"] = closed["exit_date"].dt.to_period("M")

    def _agg(g):
        wins = (g["pnl"] > 0).sum()
        return pd.Series(
            {
                "Trades": len(g),
                "Wins": int(wins),
                "Win%": round(wins / len(g) * 100, 1),
                "Net PnL": round(g["pnl"].sum(), 2),
                "Avg R": round(g["r_multiple"].mean(), 2),
                "Best Trade": round(g["pnl"].max(), 2),
                "Worst Trade": round(g["pnl"].min(), 2),
            }
        )

    result = closed.groupby("Month").apply(_agg).reset_index()
    result["Month"] = result["Month"].astype(str)
    return result


def equity_curve(df: pd.DataFrame, initial_capital: float = 100000.0) -> pd.DataFrame:
    """
    Build cumulative equity curve from closed trades sorted by exit date.
    Returns DataFrame with columns: exit_date, pnl, cumulative_pnl, equity.
    """
    closed = df[df["status"] == "CLOSED"].copy()
    if closed.empty:
        return pd.DataFrame()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"])
    closed = closed.sort_values("exit_date")
    closed["cumulative_pnl"] = closed["pnl"].cumsum()
    closed["equity"] = initial_capital + closed["cumulative_pnl"]
    return closed[["exit_date", "symbol", "pnl", "cumulative_pnl", "equity", "r_multiple"]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _schema_columns() -> list[str]:
    return [
        "trade_id", "symbol", "setup", "entry", "stop", "target1", "target2",
        "qty", "capital_used", "risk_per_share", "total_risk",
        "entry_date", "exit_price", "exit_date", "exit_reason",
        "pnl", "pnl_pct", "r_multiple", "notes", "status",
    ]


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_schema_columns())


def export_trades_json() -> str:
    """Export all trades as a formatted JSON string."""
    trades = _load_raw()
    return json.dumps(trades, indent=2, default=str)


def import_trades(json_data: list[dict] | str, replace: bool = False) -> int:
    """
    Import trades from a JSON string or list of dicts.
    If replace is True, replaces existing. Otherwise merges by trade_id.
    Returns the count of trades saved.
    """
    if isinstance(json_data, str):
        parsed = json.loads(json_data)
    else:
        parsed = json_data

    if not isinstance(parsed, list):
        raise ValueError("Invalid format: expected a list of trade objects.")

    if replace:
        _save_raw(parsed)
        return len(parsed)

    existing = _load_raw()
    existing_ids = {t.get("trade_id") for t in existing if isinstance(t, dict)}
    added = 0
    for item in parsed:
        if isinstance(item, dict):
            tid = item.get("trade_id") or str(uuid.uuid4())[:8].upper()
            item["trade_id"] = tid
            if tid not in existing_ids:
                existing.append(item)
                existing_ids.add(tid)
                added += 1
    _save_raw(existing)
    return added

