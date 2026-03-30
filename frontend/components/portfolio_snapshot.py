"""
frontend/components/portfolio_snapshot.py
──────────────────────────────────────────
Granular holdings entry screen with concentration warnings.
"""
import streamlit as st
import pandas as pd
from typing import Any, Dict, List

from frontend.api_client import APIClientError, update_client_record

_CATEGORY_TABS = [
    ("FD / Bonds", "fd_bonds_holdings", "Fixed Deposits, RD, Government Bonds, Corporate Bonds"),
    ("Debt MF", "debt_mf_holdings", "Debt Mutual Funds, Liquid Funds, Ultra Short Duration"),
    ("Equity", "equity_holdings", "Direct Stocks, Equity MF, Index Funds, ELSS"),
    ("Gold / Alt", "gold_alt_holdings", "Gold ETF, Sovereign Gold Bonds, REITs, Commodities"),
    ("Existing MF", "existing_mf_holdings", "All existing Mutual Fund SIPs and Lumpsum investments"),
]

_DEFAULT_HOLDINGS_ROW = {"Instrument": "", "Current Value (₹)": 0.0, "Purchase Date": "", "Notes": ""}


def _get_category_total(holdings: List[Dict]) -> float:
    return sum(float(h.get("Current Value (₹)", 0) or 0) for h in holdings)


def render_portfolio_snapshot(token: str, client_id: int, client_profile: Dict[str, Any]) -> None:
    st.subheader("Portfolio Snapshot — Detailed Holdings")
    st.caption("Enter all existing investments by category. The system checks for over-concentration and updates the client profile.")

    detailed_holdings = dict(client_profile.get("detailed_holdings") or {})
    category_tabs = st.tabs([ct[0] for ct in _CATEGORY_TABS])

    updated_holdings: Dict[str, List[Dict]] = {}

    for tab_ui, (tab_name, key, description) in zip(category_tabs, _CATEGORY_TABS):
        with tab_ui:
            st.caption(description)
            existing = detailed_holdings.get(key, [_DEFAULT_HOLDINGS_ROW.copy()])
            if not existing:
                existing = [_DEFAULT_HOLDINGS_ROW.copy()]

            df = pd.DataFrame(existing)
            for col in _DEFAULT_HOLDINGS_ROW:
                if col not in df.columns:
                    df[col] = _DEFAULT_HOLDINGS_ROW[col]

            edited = st.data_editor(
                df[list(_DEFAULT_HOLDINGS_ROW.keys())],
                num_rows="dynamic",
                key=f"holdings_editor_{key}_{client_id}",
                use_container_width=True,
                column_config={
                    "Current Value (₹)": st.column_config.NumberColumn("Current Value (₹)", min_value=0.0, step=1000.0),
                },
            )
            updated_holdings[key] = edited.to_dict(orient="records")

    # ── Concentration Summary ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Portfolio Concentration Summary**")

    totals = {ct[1]: _get_category_total(updated_holdings.get(ct[1], [])) for ct in _CATEGORY_TABS}
    grand_total = sum(totals.values())

    if grand_total > 0:
        summary_data = []
        for ct_name, key, _ in _CATEGORY_TABS:
            value = totals[key]
            pct = (value / grand_total * 100) if grand_total > 0 else 0
            summary_data.append({
                "Category": ct_name,
                "Total Value (₹)": f"₹{value:,.0f}",
                "Allocation (%)": f"{pct:.1f}%",
                "Status": "⚠️ Over-concentrated" if pct > 40 else "✅ OK",
            })

        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
        st.metric("Total Portfolio Value", f"₹{grand_total:,.0f}")

        for ct_name, key, _ in _CATEGORY_TABS:
            pct = (totals[key] / grand_total * 100) if grand_total > 0 else 0
            if pct > 40:
                st.warning(f"⚠️ {ct_name} represents {pct:.1f}% of your portfolio — consider diversifying.")

        try:
            import plotly.express as px
            pie_data = pd.DataFrame([
                {"Category": ct[0], "Value": totals[ct[1]]}
                for ct in _CATEGORY_TABS if totals[ct[1]] > 0
            ])
            fig = px.pie(pie_data, names="Category", values="Value", title="Portfolio Allocation", hole=0.4)
            fig.update_layout(height=350, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

    if st.button("Save Holdings Snapshot", key=f"save_holdings_{client_id}", use_container_width=True):
        try:
            update_client_record(
                token,
                client_id,
                {"profile_data": {"detailed_holdings": updated_holdings}},
            )
            st.success("Holdings snapshot saved.")
            st.rerun()
        except APIClientError as exc:
            st.error(f"Failed to save: {exc}")
