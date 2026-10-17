"""
pages/6_Heatmap.py  --  NSE Sector Heatmap
============================================
Interactive treemap-style heatmap powered by the two official NSE MCP servers:
  * cm-market    (live quotes, ~1-5 min delay)
  * nse-bhavcopy (EOD historical data)

Filters:
  - Sector multi-select
  - Stock multi-select
  - Index universe selector
  - Heatmap sizing metric (equal / by volume / by market-cap)

Color coding:
  - Deep red   → losses >= -3 %
  - Light red  → small losses
  - White/grey → flat (±0.2 %)
  - Light green → small gains
  - Deep green → gains >= +3 %
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

st.set_page_config(
    page_title="Sector Heatmap · TrendMomentum",
    page_icon="🌡️",
    layout="wide",
)

from ui.styles import inject_css
from ui.components import render_sidebar

inject_css()
settings = render_sidebar()
for k, v in settings.items():
    st.session_state[f"global_{k}"] = v

# ── Page header ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style='padding:20px 0 8px'>
        <h1 style='font-size:1.9rem;font-weight:800;
                   background:linear-gradient(135deg,#00d4aa,#388bfd);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                   background-clip:text;margin:0 0 4px'>
            🌡️ NSE Sector Heatmap
        </h1>
        <p style='color:#8b949e;font-size:0.9rem;margin:0'>
            Live market heat powered by NSE MCP servers · Color = % change · Size = weight
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Colour scale helper ───────────────────────────────────────────────────────

def pct_to_color(pct: float) -> str:
    """Map % change to a red-green color string."""
    clamp = max(-5, min(5, pct))
    if clamp >= 0:
        intensity = min(1.0, clamp / 3.0)
        r = int(0   + (1 - intensity) * 30)
        g = int(180 + intensity * 55)
        b = int(50  + (1 - intensity) * 50)
    else:
        intensity = min(1.0, abs(clamp) / 3.0)
        r = int(200 + intensity * 55)
        g = int(30  + (1 - intensity) * 30)
        b = int(30  + (1 - intensity) * 30)
    return f"rgb({r},{g},{b})"


# Plotly colorscale  (loss → gain)
HEATMAP_COLORSCALE = [
    [0.00, "#8B0000"],   # -5 %
    [0.20, "#cc2222"],   # -3 %
    [0.35, "#dd5555"],   # -1.5%
    [0.48, "#2b2b2b"],   # flat-ish
    [0.50, "#1c2128"],   # exact flat
    [0.52, "#1e3a2a"],   # tiny green
    [0.65, "#22aa55"],   # +1.5%
    [0.80, "#00cc66"],   # +3 %
    [1.00, "#00ff88"],   # +5 %
]

# ── Fallback / demo dataset ───────────────────────────────────────────────────

DEMO_DATA = [
    # symbol, change_pct, volume, market_cap, sector
    ("TCS",         1.32, 2.1e6, 14.0e12, "Nifty IT"),
    ("INFY",        0.87, 3.5e6, 7.0e12,  "Nifty IT"),
    ("HCLTECH",     2.10, 1.8e6, 4.5e12,  "Nifty IT"),
    ("WIPRO",      -0.45, 1.2e6, 2.5e12,  "Nifty IT"),
    ("TECHM",      -1.20, 0.9e6, 1.2e12,  "Nifty IT"),
    ("HDFCBANK",    0.55, 6.0e6, 12.0e12, "Nifty Bank"),
    ("ICICIBANK",   1.78, 5.5e6, 8.0e12,  "Nifty Bank"),
    ("AXISBANK",    2.30, 4.2e6, 4.5e12,  "Nifty Bank"),
    ("KOTAKBANK",  -0.90, 2.1e6, 4.0e12,  "Nifty Bank"),
    ("SBIN",        3.10, 7.8e6, 5.5e12,  "Nifty Bank"),
    ("INDUSINDBK", -2.40, 1.5e6, 1.5e12,  "Nifty Bank"),
    ("SUNPHARMA",   0.65, 1.3e6, 4.0e12,  "Nifty Pharma"),
    ("DRREDDY",    -0.33, 0.6e6, 1.9e12,  "Nifty Pharma"),
    ("CIPLA",       1.45, 1.1e6, 1.8e12,  "Nifty Pharma"),
    ("DIVISLAB",    2.80, 0.5e6, 2.1e12,  "Nifty Pharma"),
    ("MARUTI",      1.92, 0.8e6, 3.5e12,  "Nifty Auto"),
    ("TATAMOTORS",  3.55, 4.5e6, 3.0e12,  "Nifty Auto"),
    ("M&M",         2.10, 2.0e6, 3.8e12,  "Nifty Auto"),
    ("BAJAJ-AUTO",  0.72, 0.4e6, 2.2e12,  "Nifty Auto"),
    ("HEROMOTOCO", -1.10, 0.7e6, 1.8e12,  "Nifty Auto"),
    ("HINDUNILVR",  0.23, 1.5e6, 6.5e12,  "Nifty FMCG"),
    ("ITC",        -0.55, 8.5e6, 5.5e12,  "Nifty FMCG"),
    ("NESTLEIND",   0.88, 0.2e6, 2.8e12,  "Nifty FMCG"),
    ("BRITANNIA",  -0.40, 0.3e6, 1.4e12,  "Nifty FMCG"),
    ("TATASTEEL",   2.70, 5.5e6, 2.5e12,  "Nifty Metal"),
    ("JSWSTEEL",    3.20, 3.5e6, 2.2e12,  "Nifty Metal"),
    ("HINDALCO",    1.55, 2.8e6, 1.8e12,  "Nifty Metal"),
    ("COALINDIA",   0.90, 4.0e6, 2.0e12,  "Nifty Metal"),
    ("RELIANCE",   -0.33, 5.0e6, 18.0e12, "Nifty Energy"),
    ("ONGC",        1.20, 3.5e6, 2.5e12,  "Nifty Energy"),
    ("NTPC",        0.45, 4.0e6, 2.8e12,  "Nifty Energy"),
    ("POWERGRID",   0.78, 2.5e6, 2.0e12,  "Nifty Energy"),
    ("DLF",         4.20, 3.0e6, 2.1e12,  "Nifty Realty"),
    ("GODREJPROP",  2.90, 1.2e6, 1.2e12,  "Nifty Realty"),
    ("BAJFINANCE",  1.05, 2.5e6, 5.5e12,  "Nifty Fin Services"),
    ("BAJAJFINSV",  0.75, 1.0e6, 2.5e12,  "Nifty Fin Services"),
    ("SHRIRAMFIN",  2.15, 0.8e6, 1.2e12,  "Nifty Fin Services"),
    ("LT",          1.33, 1.5e6, 5.0e12,  "Nifty Infra"),
    ("ULTRACEMCO",  0.66, 0.6e6, 2.5e12,  "Nifty Infra"),
    ("BHARTIARTL", -0.22, 3.5e6, 8.0e12,  "Nifty Telecom"),
    ("TITAN",       1.88, 1.0e6, 3.5e12,  "Nifty Consumer"),
    ("ASIANPAINT", -1.30, 0.9e6, 3.0e12,  "Nifty Consumer"),
    ("APOLLOHOSP",  0.95, 0.5e6, 1.5e12,  "Nifty Healthcare"),
]

DEMO_COLS = ["symbol", "change_pct", "volume", "market_cap", "sector"]


def load_demo_df() -> pd.DataFrame:
    return pd.DataFrame(DEMO_DATA, columns=DEMO_COLS).assign(ltp=lambda d: d["market_cap"] / 1e10)


# ── Controls ─────────────────────────────────────────────────────────────────

# Top control bar
col_idx, col_size, col_refresh = st.columns([2, 2, 1])

with col_idx:
    index_choice = st.selectbox(
        "Index Universe",
        ["NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500"],
        key="hm_index",
    )

with col_size:
    size_metric = st.selectbox(
        "Tile Size",
        ["Equal Weight", "By Volume", "By Market Cap"],
        key="hm_size",
    )

with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    do_refresh = st.button("🔄 Refresh", use_container_width=True, key="hm_refresh")

# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def fetch_nse_data(index: str) -> tuple[pd.DataFrame, list[dict], str]:
    """
    Try NSE MCP servers; fall back to demo data immediately on failure.
    Returns (stocks_dataframe, live_sector_indices, source_label).
    """
    try:
        from core.nse_mcp_client import get_live_market_bundle
        stocks, sectors = get_live_market_bundle(limit=250)
        if stocks and len(stocks) >= 10:
            df = pd.DataFrame(stocks)
            if "ltp" not in df.columns and "close" in df.columns:
                df["ltp"] = df["close"]
            if "market_cap" not in df.columns:
                df["market_cap"] = 1e10
            return df, sectors, "live"
    except Exception:
        pass
    return load_demo_df(), [], "demo"


# Invalidate cache on manual refresh
if do_refresh:
    fetch_nse_data.clear()

_status_placeholder = st.empty()
_status_placeholder.info("⏳ Connecting to NSE MCP servers… (falls back to demo if offline)")

df_raw, live_sectors, _data_source = fetch_nse_data(index_choice)

_status_placeholder.empty()   # Remove loading message once data is ready

# Status badge
if _data_source == "live":
    source_label = "🟢 NSE Live MCP (cm-market)"
else:
    source_label = "🟡 Demo data — NSE MCP server offline / market closed"

st.markdown(
    f"""<div style='display:flex;align-items:center;gap:12px;margin-bottom:12px'>
        <span style='font-size:0.8rem;color:#8b949e'>{source_label}</span>
        <span style='font-size:0.8rem;color:#8b949e'>·</span>
        <span style='font-size:0.8rem;color:#8b949e'>{len(df_raw)} stocks loaded</span>
    </div>""",
    unsafe_allow_html=True,
)

# ── Sector Insight Calculations ──────────────────────────────────────────────

all_sectors = sorted(df_raw["sector"].dropna().unique().tolist())
all_stocks  = sorted(df_raw["symbol"].dropna().unique().tolist())

# Precompute baseline sector averages across all stocks
base_sector_summary = (
    df_raw.groupby("sector")
    .agg(avg_change=("change_pct", "mean"), count=("symbol", "count"))
    .sort_values("avg_change", ascending=False)
    .reset_index()
)

top_gaining_sectors = base_sector_summary.head(3)["sector"].tolist()
top_losing_sectors  = base_sector_summary.tail(3)["sector"].tolist()

# ── Top Insights Cards: Top Gaining & Losing Sectors ──────────────────────────

col_gain_sec, col_lose_sec = st.columns(2)

with col_gain_sec:
    st.markdown(
        """
        <div style='background:rgba(0,212,170,0.06);border:1px solid rgba(0,212,170,0.25);border-radius:10px;padding:12px 16px;margin-bottom:12px'>
            <div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>
                <span style='font-size:1.1rem'>🔥</span>
                <span style='font-weight:700;font-size:0.88rem;color:#00d4aa;text-transform:uppercase;letter-spacing:0.06em'>Top Gaining Sectors</span>
            </div>
            <div style='display:flex;gap:10px;flex-wrap:wrap'>
        """
        + "".join([
            f"<div style='background:#161b22;border:1px solid #238636;border-radius:6px;padding:4px 10px;font-size:0.8rem'>"
            f"<span style='color:#e6edf3;font-weight:600'>{r['sector']}</span> "
            f"<span style='color:#00ff88;font-weight:700'>{r['avg_change']:+.2f}%</span>"
            f"</div>"
            for _, r in base_sector_summary.head(3).iterrows()
        ])
        + """
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_lose_sec:
    st.markdown(
        """
        <div style='background:rgba(255,77,109,0.06);border:1px solid rgba(255,77,109,0.25);border-radius:10px;padding:12px 16px;margin-bottom:12px'>
            <div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>
                <span style='font-size:1.1rem'>❄️</span>
                <span style='font-weight:700;font-size:0.88rem;color:#ff4d6d;text-transform:uppercase;letter-spacing:0.06em'>Top Losing Sectors</span>
            </div>
            <div style='display:flex;gap:10px;flex-wrap:wrap'>
        """
        + "".join([
            f"<div style='background:#161b22;border:1px solid #da3633;border-radius:6px;padding:4px 10px;font-size:0.8rem'>"
            f"<span style='color:#e6edf3;font-weight:600'>{r['sector']}</span> "
            f"<span style='color:#ff4d6d;font-weight:700'>{r['avg_change']:+.2f}%</span>"
            f"</div>"
            for _, r in base_sector_summary.tail(3).iloc[::-1].iterrows()
        ])
        + """
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Sidebar filters ───────────────────────────────────────────────────────────

with st.sidebar:
    st.divider()
    st.markdown("**🌡️ Heatmap Filters**")

    # Quick sector preset buttons
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔥 Gainers", use_container_width=True, help="Select top 3 gaining sectors"):
            st.session_state["hm_sectors"] = top_gaining_sectors
            st.rerun()
    with col_btn2:
        if st.button("❄️ Losers", use_container_width=True, help="Select top 3 losing sectors"):
            st.session_state["hm_sectors"] = top_losing_sectors
            st.rerun()

    if "hm_sectors" not in st.session_state:
        st.session_state["hm_sectors"] = all_sectors

    selected_sectors = st.multiselect(
        "Sectors",
        options=all_sectors,
        default=st.session_state.get("hm_sectors", all_sectors),
        key="hm_sectors_widget",
    )
    # Sync state
    st.session_state["hm_sectors"] = selected_sectors

    # Stock filter scoped to selected sectors
    stocks_in_scope = sorted(
        df_raw[df_raw["sector"].isin(selected_sectors)]["symbol"].unique().tolist()
    ) if selected_sectors else []

    selected_stocks = st.multiselect(
        "Stocks (Filter Specific)",
        options=stocks_in_scope,
        default=[],
        key="hm_stocks",
        placeholder="All stocks in selected sectors",
    )

    st.divider()

    direction = st.radio(
        "Performance Filter",
        ["All Stocks", "🟢 Gainers Only (> 0%)", "🔴 Losers Only (< 0%)"],
        index=0,
        key="hm_direction",
    )

    change_min, change_max = st.slider(
        "% Change Range",
        min_value=-10.0,
        max_value=10.0,
        value=(-10.0, 10.0),
        step=0.5,
        key="hm_chng_range",
    )

# ── Filter data ───────────────────────────────────────────────────────────────

df = df_raw.copy()

if selected_sectors:
    df = df[df["sector"].isin(selected_sectors)]
else:
    df = df.iloc[0:0]

if selected_stocks:
    df = df[df["symbol"].isin(selected_stocks)]

if "Gainers" in direction:
    df = df[df["change_pct"] > 0]
elif "Losers" in direction:
    df = df[df["change_pct"] < 0]

df = df[df["change_pct"].between(change_min, change_max)]

if df.empty:
    st.warning("⚠️ No stocks match your filter criteria. Try adjusting the sector or stock selection.")
    st.stop()
    st.stop()

# ── Size column ───────────────────────────────────────────────────────────────

if size_metric == "By Volume":
    df["size_val"] = df["volume"].fillna(1).clip(lower=1)
elif size_metric == "By Market Cap":
    df["size_val"] = df["market_cap"].fillna(1e9).clip(lower=1)
else:
    df["size_val"] = 1.0

# Add root level for treemap hierarchy
df["root"] = "NSE"

# ── Top / Bottom sector summary ───────────────────────────────────────────────

sector_summary = (
    df.groupby("sector")
    .agg(avg_change=("change_pct", "mean"), count=("symbol", "count"))
    .sort_values("avg_change", ascending=False)
    .reset_index()
)

# ── Summary KPI cards ─────────────────────────────────────────────────────────

gainers_n  = int((df["change_pct"] > 0).sum())
losers_n   = int((df["change_pct"] < 0).sum())
flat_n     = int((df["change_pct"].abs() < 0.1).sum())
avg_change = df["change_pct"].mean()

top_sector   = sector_summary.iloc[0]["sector"]  if not sector_summary.empty else "—"
worst_sector = sector_summary.iloc[-1]["sector"] if not sector_summary.empty else "—"
top_chg      = sector_summary.iloc[0]["avg_change"]  if not sector_summary.empty else 0
worst_chg    = sector_summary.iloc[-1]["avg_change"] if not sector_summary.empty else 0

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

def _kpi_card(label: str, value: str, sub: str, color: str = "#e6edf3"):
    return f"""
    <div class='stat-card' style='text-align:center;padding:14px 10px'>
        <p style='color:#8b949e;font-size:0.72rem;margin:0 0 4px;text-transform:uppercase;letter-spacing:0.08em'>{label}</p>
        <p style='font-size:1.5rem;font-weight:800;color:{color};margin:0 0 2px'>{value}</p>
        <p style='color:#8b949e;font-size:0.72rem;margin:0'>{sub}</p>
    </div>"""

with kpi1:
    st.markdown(_kpi_card("Gainers", str(gainers_n), "stocks up", "#00d4aa"), unsafe_allow_html=True)
with kpi2:
    st.markdown(_kpi_card("Losers", str(losers_n), "stocks down", "#ff4d6d"), unsafe_allow_html=True)
with kpi3:
    avg_clr = "#00d4aa" if avg_change >= 0 else "#ff4d6d"
    st.markdown(_kpi_card("Avg Change", f"{avg_change:+.2f}%", "market pulse", avg_clr), unsafe_allow_html=True)
with kpi4:
    st.markdown(_kpi_card("Top Sector", top_sector, f"{top_chg:+.2f}%", "#00d4aa"), unsafe_allow_html=True)
with kpi5:
    st.markdown(_kpi_card("Weakest Sector", worst_sector, f"{worst_chg:+.2f}%", "#ff4d6d"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Treemap heatmap ───────────────────────────────────────────────────────────

def build_treemap(data: pd.DataFrame) -> go.Figure:
    """Build the main Plotly treemap with 3-level hierarchy: NSE → Sector → Stock."""
    data = data.copy()

    # Sector-level aggregates
    sector_agg = (
        data.groupby("sector")
        .agg(avg_chg=("change_pct", "mean"), total_size=("size_val", "sum"))
        .reset_index()
    )

    total_market_size = float(sector_agg["total_size"].sum())

    # ── Build flat id/parent/value/color/label arrays ───────────────────────
    ids, labels, parents, values, colors_col, hover_col = [], [], [], [], [], []

    # Root node
    ids.append("NSE")
    labels.append("NSE Market")
    parents.append("")
    values.append(total_market_size)
    colors_col.append(float(data["change_pct"].mean()))
    hover_col.append(f"<b>NSE Market</b><br>Total Stocks: {len(data)}<br>Avg Change: {data['change_pct'].mean():+.2f}%")

    # Sector nodes
    for _, row in sector_agg.iterrows():
        sector = row["sector"]
        ids.append(f"sector::{sector}")
        labels.append(sector)
        parents.append("NSE")
        values.append(float(row["total_size"]))
        colors_col.append(float(row["avg_chg"]))
        hover_col.append(
            f"<b>{sector}</b><br>"
            f"Avg Change: <b>{row['avg_chg']:+.2f}%</b><br>"
            f"Stocks: {int((data['sector'] == sector).sum())}"
        )

    # Stock leaf nodes
    for _, row in data.iterrows():
        ids.append(f"stock::{row['symbol']}")
        labels.append(f"<b>{row['symbol']}</b><br>{row['change_pct']:+.2f}%")
        parents.append(f"sector::{row['sector']}")
        values.append(float(row["size_val"]))
        colors_col.append(float(row["change_pct"]))
        hover_col.append(
            f"<b>{row['symbol']}</b><br>"
            f"Sector: {row['sector']}<br>"
            f"Change: <b>{row['change_pct']:+.2f}%</b><br>"
            f"LTP: \u20b9{row.get('ltp', 0):,.2f}<br>"
            f"Volume: {row['volume']:,.0f}<br>"
            f"Mkt Cap: \u20b9{row['market_cap'] / 1e7:,.0f} Cr"
        )

    fig = go.Figure(go.Treemap(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        customdata=hover_col,
        hovertemplate="%{customdata}<extra></extra>",
        textinfo="label",
        textfont=dict(size=11, family="Inter, system-ui, sans-serif", color="#ffffff"),
        marker=dict(
            colors=colors_col,
            colorscale=HEATMAP_COLORSCALE,
            cmid=0,
            cmin=-5,
            cmax=5,
            showscale=True,
            colorbar=dict(
                title=dict(text="% Change", font=dict(color="#8b949e", size=11)),
                tickfont=dict(color="#8b949e"),
                tickformat="+.1f",
                len=0.7,
                thickness=14,
                x=1.01,
                bgcolor="#161b22",
                bordercolor="#30363d",
                ticksuffix="%",
                tickvals=[-5, -3, -1, 0, 1, 3, 5],
                ticktext=["-5%", "-3%", "-1%", "0%", "+1%", "+3%", "+5%"],
            ),
            line=dict(color="#0d1117", width=1.5),
            pad=dict(t=20, l=3, r=3, b=3),
        ),
        pathbar=dict(
            visible=True,
            side="top",
            thickness=22,
            textfont=dict(size=11, color="#e6edf3"),
        ),
        tiling=dict(packing="squarify", pad=2),
    ))

    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        margin=dict(t=10, b=10, l=10, r=10),
        height=620,
        showlegend=False,
        font=dict(family="Inter, system-ui, sans-serif", color="#e6edf3"),
    )
    return fig



tab_treemap, tab_sector, tab_table = st.tabs(["🌡️ Heatmap", "📊 Sector Summary", "📋 Data Table"])

with tab_treemap:
    fig = build_treemap(df)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── Sector bar chart ──────────────────────────────────────────────────────────

with tab_sector:
    sector_summary_sorted = sector_summary.sort_values("avg_change")
    colors = [
        "#ff4d6d" if v < -1
        else "#dd5555" if v < 0
        else "#00cc66" if v > 1
        else "#22aa55"
        for v in sector_summary_sorted["avg_change"]
    ]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=sector_summary_sorted["avg_change"],
        y=sector_summary_sorted["sector"],
        orientation="h",
        marker_color=colors,
        marker_line=dict(color="#0d1117", width=0.5),
        text=[f"{v:+.2f}%" for v in sector_summary_sorted["avg_change"]],
        textfont=dict(color="#e6edf3", size=11),
        textposition="outside",
        customdata=sector_summary_sorted[["count"]],
        hovertemplate="<b>%{y}</b><br>Avg Change: %{x:+.2f}%<br>Stocks: %{customdata[0]}<extra></extra>",
    ))

    fig_bar.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        xaxis=dict(
            title="Average % Change",
            gridcolor="#30363d",
            zerolinecolor="#388bfd",
            tickfont=dict(color="#8b949e"),
            ticksuffix="%",
        ),
        yaxis=dict(
            gridcolor="#30363d",
            tickfont=dict(color="#e6edf3", size=11),
        ),
        margin=dict(t=20, b=40, l=160, r=80),
        height=max(300, len(sector_summary_sorted) * 42),
        font=dict(family="Inter, system-ui, sans-serif"),
        showlegend=False,
    )
    fig_bar.add_vline(x=0, line_color="#30363d", line_width=1)

    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    # Gainers vs Losers donut
    col_pie, col_heat_mini = st.columns(2)

    with col_pie:
        st.markdown("#### Breadth Snapshot")
        fig_pie = go.Figure(go.Pie(
            labels=["Gainers", "Flat", "Losers"],
            values=[gainers_n, flat_n, losers_n],
            marker_colors=["#00cc66", "#30363d", "#ff4d6d"],
            hole=0.55,
            textfont=dict(color="#e6edf3", size=12),
            hovertemplate="%{label}: <b>%{value}</b> stocks (%{percent})<extra></extra>",
        ))
        fig_pie.update_layout(
            paper_bgcolor="#0d1117",
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
            legend=dict(font=dict(color="#8b949e"), bgcolor="#0d1117"),
            font=dict(family="Inter, system-ui, sans-serif"),
            annotations=[dict(
                text=f"<b>{gainers_n + flat_n + losers_n}</b><br>Stocks",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(color="#e6edf3", size=14),
            )],
        )
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

    with col_heat_mini:
        st.markdown("#### Sector Heatgrid")
        # mini heatmap grid
        pivot = sector_summary.set_index("sector")[["avg_change"]]
        fig_mini = go.Figure(go.Heatmap(
            z=pivot["avg_change"].values.reshape(-1, 1),
            y=pivot.index.tolist(),
            x=["Avg %"],
            colorscale=HEATMAP_COLORSCALE,
            zmid=0, zmin=-5, zmax=5,
            text=[[f"{v:+.2f}%"] for v in pivot["avg_change"]],
            texttemplate="%{text}",
            showscale=False,
            hovertemplate="<b>%{y}</b><br>Avg: %{z:+.2f}%<extra></extra>",
            xgap=2, ygap=2,
        ))
        fig_mini.update_layout(
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            margin=dict(t=10, b=10, l=120, r=10),
            height=260,
            xaxis=dict(side="top", tickfont=dict(color="#8b949e")),
            yaxis=dict(tickfont=dict(color="#e6edf3", size=10)),
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig_mini, use_container_width=True, config={"displayModeBar": False})

# ── Data table ────────────────────────────────────────────────────────────────

with tab_table:
    col_sort, col_dload = st.columns([3, 1])
    with col_sort:
        sort_col = st.selectbox("Sort by", ["change_pct", "symbol", "sector", "volume", "market_cap"], key="hm_sort")
    with col_dload:
        st.markdown("<br>", unsafe_allow_html=True)

    display_df = (
        df[["symbol", "sector", "ltp", "change_pct", "volume", "market_cap"]]
        .sort_values(sort_col, ascending=(sort_col == "symbol"))
        .reset_index(drop=True)
    )
    display_df.columns = ["Symbol", "Sector", "LTP (₹)", "Change %", "Volume", "Mkt Cap (₹)"]

    def color_change(val):
        if val > 2:
            return "background-color:#003020;color:#00ff88"
        elif val > 0:
            return "background-color:#001a0f;color:#00cc66"
        elif val < -2:
            return "background-color:#200010;color:#ff4d6d"
        elif val < 0:
            return "background-color:#1a0008;color:#dd5555"
        return "color:#8b949e"

    styler = display_df.style
    if hasattr(styler, "map"):
        styler = styler.map(color_change, subset=["Change %"])
    else:
        styler = styler.applymap(color_change, subset=["Change %"])

    styled = (
        styler
        .format({
            "LTP (₹)":    "₹{:,.2f}",
            "Change %":   "{:+.2f}%",
            "Volume":     "{:,.0f}",
            "Mkt Cap (₹)": "₹{:,.0f}",
        })
        .set_properties(**{
            "background-color": "#161b22",
            "color": "#e6edf3",
            "border": "1px solid #30363d",
        })
        .set_table_styles([
            {"selector": "th", "props": [
                ("background-color", "#1c2128"),
                ("color", "#8b949e"),
                ("font-weight", "600"),
                ("text-align", "center"),
            ]},
        ])
    )

    st.dataframe(styled, use_container_width=True, height=500)

    # Download button
    csv_data = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv_data,
        file_name="nse_heatmap.csv",
        mime="text/csv",
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    """<p style='color:#8b949e;font-size:0.72rem;text-align:center'>
    Data sourced from NSE MCP servers (mcp.nseindia.in) · ~1-5 min delay during market hours ·
    ⚠️ For educational purposes only. Not investment advice.
    </p>""",
    unsafe_allow_html=True,
)
