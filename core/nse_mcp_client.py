"""
core/nse_mcp_client.py
-----------------------
Async client for the two official NSE MCP servers:
  - nse-bhavcopy: https://mcp.nseindia.in/bhavcopy/cm/mcp
  - cm-market   : https://mcp.nseindia.in/cmmkt/mcp

Both endpoints use Streamable-HTTP transport (MCP SDK >= 1.3).
All public functions are synchronous wrappers so Streamlit can call them
without managing an event loop.

Timeouts are kept tight (8s per call) so the page falls back to
demo data quickly when the NSE servers are unreachable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

# Suppress noisy session cleanup 501 messages from anyio/mcp
logging.getLogger("mcp").setLevel(logging.ERROR)
logging.getLogger("anyio").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Comprehensive Sector -> Stock Mapping (Top NSE Stocks)
# ---------------------------------------------------------------------------

STOCK_SECTOR_MAP: dict[str, str] = {
    # Nifty IT
    "TCS": "Nifty IT", "INFY": "Nifty IT", "HCLTECH": "Nifty IT",
    "WIPRO": "Nifty IT", "TECHM": "Nifty IT", "LTIM": "Nifty IT",
    "MPHASIS": "Nifty IT", "COFORGE": "Nifty IT", "PERSISTENT": "Nifty IT",
    "LTTS": "Nifty IT", "OFSS": "Nifty IT", "TATAELXSI": "Nifty IT",
    "KPITTECH": "Nifty IT", "CYIENT": "Nifty IT", "ZENSARTECH": "Nifty IT",
    "SONATSOFTW": "Nifty IT", "BSOFT": "Nifty IT", "HEXAWARE": "Nifty IT",

    # Nifty Bank
    "HDFCBANK": "Nifty Bank", "ICICIBANK": "Nifty Bank", "AXISBANK": "Nifty Bank",
    "KOTAKBANK": "Nifty Bank", "SBIN": "Nifty Bank", "INDUSINDBK": "Nifty Bank",
    "FEDERALBNK": "Nifty Bank", "IDFCFIRSTB": "Nifty Bank", "AUBANK": "Nifty Bank",
    "BANDHANBNK": "Nifty Bank", "PNB": "Nifty Bank", "BANKINDIA": "Nifty Bank",
    "CANBK": "Nifty Bank", "BANKBARODA": "Nifty Bank", "UNIONBANK": "Nifty Bank",
    "IOB": "Nifty Bank", "UCOBANK": "Nifty Bank", "CENTRALBK": "Nifty Bank",

    # Nifty Pharma & Healthcare
    "SUNPHARMA": "Nifty Pharma", "DRREDDY": "Nifty Pharma", "CIPLA": "Nifty Pharma",
    "DIVISLAB": "Nifty Pharma", "BIOCON": "Nifty Pharma", "AUROPHARMA": "Nifty Pharma",
    "LUPIN": "Nifty Pharma", "TORNTPHARM": "Nifty Pharma", "ALKEM": "Nifty Pharma",
    "ZYDUSLIFE": "Nifty Pharma", "GLENMARK": "Nifty Pharma", "MANKIND": "Nifty Pharma",
    "IPCALAB": "Nifty Pharma", "ABBOTINDIA": "Nifty Pharma", "GLAXO": "Nifty Pharma",
    "APOLLOHOSP": "Nifty Healthcare", "MAXHEALTH": "Nifty Healthcare",
    "FORTIS": "Nifty Healthcare", "MEDANTA": "Nifty Healthcare", "NH": "Nifty Healthcare",

    # Nifty Auto
    "MARUTI": "Nifty Auto", "TATAMOTORS": "Nifty Auto", "M&M": "Nifty Auto",
    "BAJAJ-AUTO": "Nifty Auto", "HEROMOTOCO": "Nifty Auto", "EICHERMOT": "Nifty Auto",
    "TVSMOTOR": "Nifty Auto", "BALKRISIND": "Nifty Auto", "APOLLOTYRE": "Nifty Auto",
    "BHARATFORG": "Nifty Auto", "ASHOKLEY": "Nifty Auto", "MOTHERSON": "Nifty Auto",
    "EXIDEIND": "Nifty Auto", "AMARAJABAT": "Nifty Auto", "MRF": "Nifty Auto",
    "BOSCHLTD": "Nifty Auto", "TIINDIA": "Nifty Auto",

    # Nifty FMCG
    "HINDUNILVR": "Nifty FMCG", "ITC": "Nifty FMCG", "NESTLEIND": "Nifty FMCG",
    "BRITANNIA": "Nifty FMCG", "GODREJCP": "Nifty FMCG", "TATACONSUM": "Nifty FMCG",
    "DABUR": "Nifty FMCG", "MARICO": "Nifty FMCG", "COLPAL": "Nifty FMCG",
    "VBL": "Nifty FMCG", "EMAMILTD": "Nifty FMCG", "RADICO": "Nifty FMCG",
    "UBL": "Nifty FMCG", "PGHH": "Nifty FMCG", "PATANJALI": "Nifty FMCG",

    # Nifty Metal
    "TATASTEEL": "Nifty Metal", "JSWSTEEL": "Nifty Metal", "HINDALCO": "Nifty Metal",
    "COALINDIA": "Nifty Metal", "VEDL": "Nifty Metal", "SAIL": "Nifty Metal",
    "APLAPOLLO": "Nifty Metal", "NATIONALUM": "Nifty Metal", "JINDALSTEL": "Nifty Metal",
    "NMDC": "Nifty Metal", "HINDZINC": "Nifty Metal", "RATNAMANI": "Nifty Metal",

    # Nifty Energy & Oil/Gas
    "RELIANCE": "Nifty Energy", "ONGC": "Nifty Energy", "NTPC": "Nifty Energy",
    "POWERGRID": "Nifty Energy", "BPCL": "Nifty Energy", "IOC": "Nifty Energy",
    "ADANIGREEN": "Nifty Energy", "TATAPOWER": "Nifty Energy", "GAIL": "Nifty Energy",
    "ADANIENT": "Nifty Energy", "ADANIPOWER": "Nifty Energy", "OIL": "Nifty Energy",
    "PETRONET": "Nifty Energy", "HINDPETRO": "Nifty Energy", "IGL": "Nifty Energy",
    "MGL": "Nifty Energy", "GUJGASLTD": "Nifty Energy", "SUZLON": "Nifty Energy",

    # Nifty Realty
    "DLF": "Nifty Realty", "GODREJPROP": "Nifty Realty", "OBEROIRLTY": "Nifty Realty",
    "PRESTIGE": "Nifty Realty", "LODHA": "Nifty Realty", "BRIGADE": "Nifty Realty",
    "PHOENIXLTD": "Nifty Realty", "SOBHA": "Nifty Realty", "SUNTECK": "Nifty Realty",

    # Nifty Financial Services
    "BAJFINANCE": "Nifty Fin Services", "BAJAJFINSV": "Nifty Fin Services",
    "SHRIRAMFIN": "Nifty Fin Services", "MUTHOOTFIN": "Nifty Fin Services",
    "JIOFIN": "Nifty Fin Services", "CHOLAFIN": "Nifty Fin Services",
    "HDFCLIFE": "Nifty Fin Services", "SBILIFE": "Nifty Fin Services",
    "ICICIPRULI": "Nifty Fin Services", "PFC": "Nifty Fin Services",
    "RECLTD": "Nifty Fin Services", "ICICIGI": "Nifty Fin Services",

    # Nifty Infrastructure & Cement
    "LT": "Nifty Infra", "ULTRACEMCO": "Nifty Infra", "GRASIM": "Nifty Infra",
    "ADANIPORTS": "Nifty Infra", "AMBUJACEM": "Nifty Infra", "ACC": "Nifty Infra",
    "SHREECEM": "Nifty Infra", "GMRINFRA": "Nifty Infra", "IRCTC": "Nifty Infra",
    "IRFC": "Nifty Infra", "RVNL": "Nifty Infra",

    # Nifty Consumer & Retail
    "TITAN": "Nifty Consumer", "ASIANPAINT": "Nifty Consumer", "TRENT": "Nifty Retail",
    "BERGEPAINT": "Nifty Consumer", "VOLTAS": "Nifty Consumer", "HAVELLS": "Nifty Consumer",
    "POLYCAB": "Nifty Consumer", "DIXON": "Nifty Consumer", "KALYANKJIL": "Nifty Consumer",
    "BATAINDIA": "Nifty Consumer", "PAGEIND": "Nifty Consumer", "DMART": "Nifty Retail",
    "NYKAA": "Nifty Retail", "ZOMATO": "Nifty Retail",

    # Nifty Telecom & Media
    "BHARTIARTL": "Nifty Telecom", "TATACOMM": "Nifty Telecom",
    "INDUSTOWER": "Nifty Telecom", "IDEA": "Nifty Telecom",
    "ZEEL": "Nifty Media", "SUNTV": "Nifty Media", "PVRINOX": "Nifty Media",
    "NAZARA": "Nifty Media",

    # Nifty Defence & Aviation
    "BEL": "Nifty Defence", "HAL": "Nifty Defence", "MAZDOCK": "Nifty Defence",
    "BDL": "Nifty Defence", "COCHINSHIP": "Nifty Defence", "INDIGO": "Nifty Aviation",
    "SPICEJET": "Nifty Aviation",

    # Nifty Chemicals
    "SRF": "Nifty Chemicals", "PIDILITIND": "Nifty Chemicals", "PIIND": "Nifty Chemicals",
    "FLUOROCHEM": "Nifty Chemicals", "DEEPAKNTR": "Nifty Chemicals", "TATACHEM": "Nifty Chemicals",
}

NSE_BHAVCOPY_URL = "https://mcp.nseindia.in/bhavcopy/cm/mcp"
NSE_CMMARKET_URL = "https://mcp.nseindia.in/cmmkt/mcp"

_TIMEOUT_S = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _extract_records(raw: Any) -> list[dict]:
    """Unwrap MCP response into a flat list of dicts."""
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        for key in ("stocks", "data", "records", "results", "items", "securities", "gainers", "losers"):
            if key in raw and isinstance(raw[key], list):
                return [r for r in raw[key] if isinstance(r, dict)]
    return []


# ---------------------------------------------------------------------------
# Async MCP Fetchers
# ---------------------------------------------------------------------------

async def _fetch_cmmarket_bundle_async(limit: int = 250) -> tuple[list[dict], list[dict]]:
    """
    Fetch both sectoral indices and live equity stocks in a SINGLE MCP session.
    Returns (stocks, sectoral_indices).
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    stocks_raw: list[dict] = []
    sectors_raw: list[dict] = []

    try:
        async with streamablehttp_client(NSE_CMMARKET_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=_TIMEOUT_S)

                # 1. Fetch live sectoral indices
                try:
                    res_sec = await asyncio.wait_for(
                        session.call_tool("cm_get_live_indices", {"group": "sectoral", "nameFilter": ""}),
                        timeout=_TIMEOUT_S,
                    )
                    if res_sec.content:
                        sec_json = json.loads(res_sec.content[0].text)  # type: ignore[union-attr]
                        ind_dict = sec_json.get("indices", {})
                        if isinstance(ind_dict, dict):
                            sectors_raw = ind_dict.get("sectoral", [])
                        elif isinstance(ind_dict, list):
                            sectors_raw = ind_dict
                except Exception:
                    sectors_raw = []

                # 2. Fetch market movers (gainers + losers)
                try:
                    res_mov = await asyncio.wait_for(
                        session.call_tool("nse_get_market_movers", {"indexName": "NIFTY", "limit": 50}),
                        timeout=_TIMEOUT_S,
                    )
                    if res_mov.content:
                        mov_json = json.loads(res_mov.content[0].text)  # type: ignore[union-attr]
                        stocks_raw.extend(mov_json.get("gainers", []))
                        stocks_raw.extend(mov_json.get("losers", []))
                except Exception:
                    pass

                # 3. Fetch broader equity stocks
                try:
                    res_eq = await asyncio.wait_for(
                        session.call_tool("cm_get_equity_stocks", {"limit": limit, "symbolFilter": ""}),
                        timeout=_TIMEOUT_S,
                    )
                    if res_eq.content:
                        eq_json = json.loads(res_eq.content[0].text)  # type: ignore[union-attr]
                        stocks_raw.extend(eq_json.get("stocks", []))
                except Exception:
                    pass
    except Exception:
        pass

    return stocks_raw, sectors_raw


async def _call_single_tool_async(server_url: str, tool_name: str, args: dict) -> Any:
    """Call a single tool on an MCP server."""
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=_TIMEOUT_S)
                result = await asyncio.wait_for(session.call_tool(tool_name, args), timeout=_TIMEOUT_S)
                if result.content:
                    raw = result.content[0].text  # type: ignore[union-attr]
                    try:
                        return json.loads(raw)
                    except Exception:
                        return raw
        return {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Sync Thread Pool Runner
# ---------------------------------------------------------------------------

def _run(coro) -> Any:
    """Run async coroutine in a background thread to prevent loop conflict."""
    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(asyncio.run, coro)
            return fut.result(timeout=_TIMEOUT_S + 6)
    except Exception:
        return None


def call_cmmarket(tool_name: str, args: dict = {}) -> Any:
    return _run(_call_single_tool_async(NSE_CMMARKET_URL, tool_name, args)) or {}


def call_bhavcopy(tool_name: str, args: dict = {}) -> Any:
    return _run(_call_single_tool_async(NSE_BHAVCOPY_URL, tool_name, args)) or {}


# ---------------------------------------------------------------------------
# High-Level Heatmap & Sector APIs
# ---------------------------------------------------------------------------

def get_live_market_bundle(limit: int = 250) -> tuple[list[dict], list[dict]]:
    """
    Fetch both stocks and sector indices from the NSE MCP server.
    Returns (cleaned_stocks, cleaned_sectors).
    """
    raw_stocks, raw_sectors = _run(_fetch_cmmarket_bundle_async(limit)) or ([], [])

    # Process stocks (deduplicate by symbol)
    seen_symbols: set[str] = set()
    cleaned_stocks: list[dict] = []

    for r in raw_stocks:
        symbol = str(r.get("symbol") or r.get("Symbol") or "").strip().upper()
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)

        ltp = _safe_float(
            r.get("lastTradedPrice") or r.get("lastPrice") or r.get("ltp") or
            r.get("close") or r.get("price") or 0
        )
        pchng = _safe_float(
            r.get("perChange") or r.get("pChange") or r.get("pchng") or
            r.get("change_pct") or 0
        )
        vol = _safe_float(
            r.get("volume") or r.get("trade_quantity") or
            r.get("totalTradedVolume") or r.get("qty") or 0
        )
        val = _safe_float(r.get("value") or r.get("turnover") or 0)
        mcap = _safe_float(r.get("marketCap") or r.get("mcap") or 0)
        if mcap <= 0 and val > 0:
            mcap = val * 1e7
        if mcap <= 0:
            mcap = 1e9

        sector = STOCK_SECTOR_MAP.get(symbol, "Others")

        cleaned_stocks.append({
            "symbol": symbol,
            "ltp": ltp,
            "change_pct": pchng,
            "volume": vol,
            "market_cap": mcap,
            "sector": sector,
        })

    # Process sectors
    cleaned_sectors: list[dict] = []
    for item in raw_sectors:
        name = str(item.get("indexName") or "").strip()
        if not name:
            continue
        # Convert 'NIFTY IT' -> 'Nifty IT'
        clean_name = name.title().replace("Nifty", "Nifty").replace("Finsrv", "Fin Services")
        cleaned_sectors.append({
            "sector": clean_name,
            "raw_name": name,
            "change_pct": _safe_float(item.get("percChange") or item.get("changePct") or 0),
            "last": _safe_float(item.get("last") or 0),
            "change": _safe_float(item.get("change") or 0),
        })

    return cleaned_stocks, cleaned_sectors


def get_heatmap_data(index: str = "NIFTY 50", use_live: bool = True) -> list[dict]:
    """
    Master entry point for Heatmap: returns stocks with sectors assigned.
    """
    if not use_live:
        return []
    stocks, _ = get_live_market_bundle(limit=250)
    return stocks
