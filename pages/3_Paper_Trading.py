"""
pages/3_Paper_Trading.py  —  Paper Trading Journal
====================================================
Track simulated trades, monitor open positions with live P&L,
and view monthly performance reports.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="Paper Trading · TrendMomentum", page_icon="📋", layout="wide")

from ui.styles import inject_css, badge, stat_card_html
from ui.components import (
    render_sidebar,
    plot_equity_curve,
    plot_monthly_pnl,
)
from core.paper_book import (
    load_trades,
    add_trade,
    close_trade,
    update_trade,
    delete_trade,
    monthly_stats,
    equity_curve,
    export_trades_json,
    import_trades,
)
from core.scanner_engine import get_history


inject_css()
settings = render_sidebar()
capital = settings["capital"]

# ── Page header ───────────────────────────────────────────────────────────
st.markdown(
    "<h1>📋 Paper Trading Journal</h1>"
    "<p style='color:#8b949e;margin-top:-8px'>"
    "Simulate trades risk-free. Track open positions with live P&L and review monthly performance.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Load data ─────────────────────────────────────────────────────────────
df = load_trades()
open_trades = df[df["status"] == "OPEN"] if not df.empty else pd.DataFrame()
closed_trades = df[df["status"] == "CLOSED"] if not df.empty else pd.DataFrame()

# ── Top-level summary ─────────────────────────────────────────────────────
total_open = len(open_trades)
total_closed = len(closed_trades)
net_pnl = closed_trades["pnl"].sum() if not closed_trades.empty else 0.0
win_rate = (
    (closed_trades["pnl"] > 0).mean() * 100 if not closed_trades.empty else 0.0
)
avg_r = closed_trades["r_multiple"].mean() if not closed_trades.empty else 0.0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("📂 Open Positions", total_open)
m2.metric("✅ Closed Trades", total_closed)
net_color = "normal" if net_pnl >= 0 else "inverse"
m3.metric("💰 Net P&L", f"₹{net_pnl:+,.0f}", delta_color=net_color)
m4.metric("🎯 Win Rate", f"{win_rate:.1f}%")
m5.metric("📐 Avg R Multiple", f"{avg_r:.2f}R")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────
tab_open, tab_close, tab_report, tab_add, tab_backup = st.tabs([
    f"🟢 Open ({total_open})",
    f"📁 History ({total_closed})",
    "📊 Monthly Report",
    "➕ Add Trade",
    "💾 Backup & Data",
])



# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — OPEN POSITIONS
# ═══════════════════════════════════════════════════════════════════════════
with tab_open:
    if open_trades.empty:
        st.info("No open paper trades. Add a trade from the **Trade Planner** or use the ➕ tab.")
    else:
        for _, t in open_trades.iterrows():
            tid = t["trade_id"]
            sym = t["symbol"]
            entry = float(t["entry"])
            stop = float(t["stop"])
            tgt1 = float(t["target1"])
            tgt2 = float(t["target2"])
            qty = int(t["qty"])
            entry_date = t["entry_date"]

            # ── Try to get live CMP ────────────────────────────────────────
            cmp = None
            try:
                ticker_sym = sym if sym.endswith(".NS") else f"{sym}.NS"
                df_live = get_history(ticker_sym, "5d", "1d")
                if not df_live.empty:
                    cmp = float(df_live["Close"].iloc[-1])
            except Exception:
                pass

            live_pnl = (cmp - entry) * qty if cmp else None
            live_pnl_pct = ((cmp / entry) - 1) * 100 if cmp else None
            days_held = (date.today() - date.fromisoformat(str(entry_date))).days if entry_date else "—"

            # ── Distance to levels ────────────────────────────────────────
            dist_stop = ((cmp - stop) / entry * 100) if cmp else None
            dist_t1 = ((tgt1 - cmp) / entry * 100) if cmp else None

            pnl_color = "positive" if (live_pnl or 0) >= 0 else "negative"

            with st.container(border=True):
                col_info, col_metrics, col_actions = st.columns([2, 3, 2])

                with col_info:
                    signal_badge = badge("OPEN", "open")
                    st.markdown(
                        f"<h3 style='margin:0'>{sym} {signal_badge}</h3>"
                        f"<p style='color:#8b949e;font-size:0.78rem;margin:4px 0 0'>"
                        f"Entry: <b style='color:#e6edf3'>₹{entry:,.2f}</b> · "
                        f"Qty: <b style='color:#e6edf3'>{qty}</b> · "
                        f"Held: <b style='color:#e6edf3'>{days_held}d</b></p>"
                        f"<p style='color:#8b949e;font-size:0.78rem;margin:2px 0 0'>"
                        f"Setup: <b style='color:#e6edf3'>{t.get('setup','—')}</b></p>",
                        unsafe_allow_html=True,
                    )

                with col_metrics:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("CMP", f"₹{cmp:,.2f}" if cmp else "—")
                    c2.metric(
                        "Live P&L",
                        f"₹{live_pnl:+,.0f}" if live_pnl is not None else "—",
                        f"{live_pnl_pct:+.1f}%" if live_pnl_pct is not None else None,
                        delta_color="normal" if (live_pnl or 0) >= 0 else "inverse",
                    )
                    c3.metric("Stop", f"₹{stop:,.2f}", f"{dist_stop:+.1f}% from CMP" if dist_stop else None, delta_color="off")
                    c4.metric("T1", f"₹{tgt1:,.2f}", f"{dist_t1:+.1f}% away" if dist_t1 else None, delta_color="off")

                with col_actions:
                    st.markdown("**Exit Trade**")
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if cmp and st.button(f"T1 ₹{tgt1:,.0f}", key=f"exit_t1_{tid}", use_container_width=True):
                            if close_trade(tid, tgt1, "Target 1"):
                                st.toast(f"✅ {sym} closed at T1 ₹{tgt1:,.2f}", icon="🎯")
                                st.rerun()
                        if cmp and st.button(f"Stop ₹{stop:,.0f}", key=f"exit_sl_{tid}", use_container_width=True):
                            if close_trade(tid, stop, "Stop Loss"):
                                st.toast(f"🛑 {sym} stopped out at ₹{stop:,.2f}", icon="🛑")
                                st.rerun()
                    with col_b2:
                        if cmp and st.button(f"T2 ₹{tgt2:,.0f}", key=f"exit_t2_{tid}", use_container_width=True):
                            if close_trade(tid, tgt2, "Target 2"):
                                st.toast(f"🚀 {sym} closed at T2 ₹{tgt2:,.2f}", icon="🚀")
                                st.rerun()
                        if st.button("✏️ Custom", key=f"exit_cust_{tid}", use_container_width=True):
                            st.session_state[f"custom_exit_{tid}"] = True

                # Custom exit form
                if st.session_state.get(f"custom_exit_{tid}"):
                    with st.form(f"form_custom_{tid}"):
                        cex_price = st.number_input("Exit Price", min_value=0.01, value=float(cmp or entry), step=0.5)
                        cex_reason = st.selectbox("Reason", ["Manual", "Target 1", "Target 2", "Stop Loss", "Trailing Stop"])
                        cex_notes = st.text_input("Notes (optional)")
                        if st.form_submit_button("✅ Confirm Exit", type="primary"):
                            close_trade(tid, cex_price, cex_reason, notes=cex_notes)
                            st.session_state.pop(f"custom_exit_{tid}", None)
                            st.toast(f"{sym} closed at ₹{cex_price:,.2f}", icon="✅")
                            st.rerun()
                        if st.form_submit_button("Cancel"):
                            st.session_state.pop(f"custom_exit_{tid}", None)
                            st.rerun()

                # Edit stop / target
                with st.expander("🔧 Edit Stop / Targets / Notes", expanded=False):
                    ef1, ef2, ef3 = st.columns(3)
                    with ef1:
                        new_stop = st.number_input("New Stop ₹", 0.01, value=float(stop), step=0.5, key=f"ns_{tid}")
                    with ef2:
                        new_t1 = st.number_input("New T1 ₹", 0.01, value=float(tgt1), step=0.5, key=f"nt1_{tid}")
                    with ef3:
                        new_notes = st.text_input("Notes", value=str(t.get("notes", "")), key=f"nn_{tid}")
                    if st.button("💾 Save Changes", key=f"save_{tid}"):
                        update_trade(tid, stop=new_stop, target1=new_t1, notes=new_notes)
                        st.toast(f"{sym} updated.", icon="💾")
                        st.rerun()

                # Delete
                with st.expander("🗑️ Delete Trade"):
                    st.warning("This permanently removes the trade record.")
                    if st.button("🗑️ Delete", key=f"del_{tid}", type="secondary"):
                        delete_trade(tid)
                        st.toast(f"{sym} deleted.", icon="🗑️")
                        st.rerun()

            st.markdown("")  # spacing


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — TRADE HISTORY
# ═══════════════════════════════════════════════════════════════════════════
with tab_close:
    if closed_trades.empty:
        st.info("No closed trades yet.")
    else:
        # Summary filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filt_sym = st.text_input("Filter by Symbol", placeholder="e.g. SBIN", key="hist_sym").strip().upper()
        with col_f2:
            filt_outcome = st.selectbox("Filter by Outcome", ["All", "Profitable", "Loss", "Target 1", "Target 2", "Stop Loss"])

        disp = closed_trades.copy()
        if filt_sym:
            disp = disp[disp["symbol"].str.contains(filt_sym, na=False)]
        if filt_outcome == "Profitable":
            disp = disp[disp["pnl"] > 0]
        elif filt_outcome == "Loss":
            disp = disp[disp["pnl"] < 0]
        elif filt_outcome in ("Target 1", "Target 2", "Stop Loss"):
            disp = disp[disp["exit_reason"] == filt_outcome]

        st.dataframe(
            disp[[
                "trade_id", "symbol", "setup", "entry_date", "exit_date",
                "entry", "exit_price", "qty", "exit_reason",
                "pnl", "pnl_pct", "r_multiple", "notes"
            ]].rename(columns={
                "trade_id": "ID", "symbol": "Symbol", "setup": "Setup",
                "entry_date": "Entry Date", "exit_date": "Exit Date",
                "entry": "Entry ₹", "exit_price": "Exit ₹", "qty": "Qty",
                "exit_reason": "Reason", "pnl": "P&L ₹",
                "pnl_pct": "P&L %", "r_multiple": "R Multiple", "notes": "Notes",
            }),
            use_container_width=True,
            hide_index=True,
            column_config={
                "P&L ₹": st.column_config.NumberColumn("P&L ₹", format="₹%.0f"),
                "P&L %": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
                "R Multiple": st.column_config.NumberColumn("R", format="%.2f"),
                "Entry ₹": st.column_config.NumberColumn("Entry ₹", format="%.2f"),
                "Exit ₹": st.column_config.NumberColumn("Exit ₹", format="%.2f"),
            },
        )

        st.download_button(
            "📥 Download History CSV",
            disp.to_csv(index=False),
            "paper_trades.csv",
            "text/csv",
        )


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — MONTHLY REPORT
# ═══════════════════════════════════════════════════════════════════════════
with tab_report:
    if closed_trades.empty:
        st.info("Close some trades first to see the monthly performance report.")
    else:
        # ── Equity curve ──────────────────────────────────────────────────
        st.markdown("### 📈 Portfolio Equity Curve")
        eq_df = equity_curve(df, initial_capital=capital)
        plot_equity_curve(eq_df, initial_capital=capital)

        st.divider()

        # ── Monthly P&L bars ──────────────────────────────────────────────
        st.markdown("### 📅 Monthly P&L")
        mon_df = monthly_stats(df)
        if not mon_df.empty:
            plot_monthly_pnl(mon_df)

            # Monthly table
            st.dataframe(
                mon_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Win%": st.column_config.NumberColumn("Win %", format="%.1f%%"),
                    "Net PnL": st.column_config.NumberColumn("Net P&L ₹", format="₹%.0f"),
                    "Avg R": st.column_config.NumberColumn("Avg R", format="%.2f"),
                    "Best Trade": st.column_config.NumberColumn("Best ₹", format="₹%.0f"),
                    "Worst Trade": st.column_config.NumberColumn("Worst ₹", format="₹%.0f"),
                },
            )

        st.divider()

        # ── All-time stats ────────────────────────────────────────────────
        st.markdown("### 🏆 All-Time Statistics")
        gross_wins = closed_trades[closed_trades["pnl"] > 0]["pnl"].sum()
        gross_loss = abs(closed_trades[closed_trades["pnl"] < 0]["pnl"].sum())
        profit_factor = (gross_wins / gross_loss) if gross_loss > 0 else float("inf")
        best_trade = closed_trades["pnl"].max() if not closed_trades.empty else 0
        worst_trade = closed_trades["pnl"].min() if not closed_trades.empty else 0
        avg_win = closed_trades[closed_trades["pnl"] > 0]["pnl"].mean() if any(closed_trades["pnl"] > 0) else 0
        avg_loss = closed_trades[closed_trades["pnl"] < 0]["pnl"].mean() if any(closed_trades["pnl"] < 0) else 0

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total P&L", f"₹{net_pnl:+,.0f}")
        s2.metric("Win Rate", f"{win_rate:.1f}%")
        s3.metric("Profit Factor", f"{profit_factor:.2f}")
        s4.metric("Avg R Multiple", f"{avg_r:.2f}R")

        s5, s6, s7, s8 = st.columns(4)
        s5.metric("Best Trade", f"₹{best_trade:+,.0f}")
        s6.metric("Worst Trade", f"₹{worst_trade:+,.0f}")
        s7.metric("Avg Win", f"₹{avg_win:+,.0f}")
        s8.metric("Avg Loss", f"₹{avg_loss:+,.0f}")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — MANUAL ADD TRADE
# ═══════════════════════════════════════════════════════════════════════════
with tab_add:
    st.markdown("##### Manually add a paper trade to the journal")
    st.caption("Tip: Use the Trade Planner page to add trades automatically with calculated sizing.")

    with st.form("manual_add_form"):
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            a_sym = st.text_input("Symbol *", placeholder="e.g. SBIN").strip().upper()
            a_entry = st.number_input("Entry Price ₹ *", min_value=0.05, value=1000.0, step=0.5)
            a_stop = st.number_input("Stop Loss ₹ *", min_value=0.01, value=970.0, step=0.5)
        with col_a2:
            a_setup = st.selectbox("Setup Type", ["Breakout", "Trend", "Pullback", "Reversal", "Other"])
            a_t1 = st.number_input("Target 1 ₹", min_value=0.05, value=1060.0, step=0.5)
            a_t2 = st.number_input("Target 2 ₹", min_value=0.05, value=1090.0, step=0.5)

        a_qty = st.number_input("Quantity (shares) *", min_value=1, value=10)
        a_notes = st.text_area("Notes (optional)", height=68)

        submitted = st.form_submit_button("➕ Add Trade to Journal", type="primary", use_container_width=True)

        if submitted:
            if not a_sym:
                st.error("Symbol is required.")
            elif a_stop >= a_entry:
                st.error("Stop must be below entry.")
            elif a_t1 <= a_entry:
                st.error("Target 1 must be above entry.")
            else:
                trade_id = add_trade(
                    a_sym, a_setup, a_entry, a_stop, a_t1, a_t2, a_qty,
                    capital=a_qty * a_entry,
                    notes=a_notes,
                )
                st.success(f"✅ Trade added! ID: **{trade_id}** — {a_sym} {a_qty}×₹{a_entry:.2f}")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 — BACKUP & DATA PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════
with tab_backup:
    st.markdown("##### 💾 Paper Trades Storage & Backup")
    st.info(
        "💡 **Automatic Persistence:** All your paper trades are saved permanently to disk at `data/paper_trades.json`. "
        "They remain saved across app restarts, browser closes, and page refreshes."
    )

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.markdown("###### 📥 Export / Download Backup")
        st.caption("Download a copy of your paper trading journal to keep a local backup.")
        json_data = export_trades_json()
        st.download_button(
            "📥 Download Backup (JSON)",
            json_data,
            file_name=f"paper_trades_backup_{date.today().isoformat()}.json",
            mime="application/json",
            use_container_width=True,
        )
        if not df.empty:
            st.download_button(
                "📊 Export All Trades (CSV)",
                df.to_csv(index=False),
                file_name=f"paper_trades_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with col_b2:
        st.markdown("###### 📤 Restore from Backup")
        st.caption("Upload a previously saved `paper_trades_backup.json` to restore your trades.")
        uploaded_backup = st.file_uploader("Choose backup JSON file", type=["json"], key="backup_uploader")
        if uploaded_backup is not None:
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if st.button("🔄 Merge Trades", type="primary", use_container_width=True):
                    try:
                        content = uploaded_backup.getvalue().decode("utf-8")
                        count = import_trades(content, replace=False)
                        st.success(f"✅ Successfully merged {count} trades!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error importing backup: {e}")
            with col_m2:
                if st.button("⚠️ Replace All", use_container_width=True):
                    try:
                        content = uploaded_backup.getvalue().decode("utf-8")
                        count = import_trades(content, replace=True)
                        st.success(f"✅ Successfully replaced journal with {count} trades!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error importing backup: {e}")

