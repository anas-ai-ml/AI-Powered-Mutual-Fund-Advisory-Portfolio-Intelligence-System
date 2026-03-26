from typing import Any, Dict, Optional

import streamlit as st
from backend.engines.intelligence.context_engine import get_macro_context
from backend.utils.sip_calculator import calculate_sip_future_value
from backend.processors.output_formatter import build_projection_assumptions
from frontend.components.projection_panels import (
    build_projection_timeline_table,
    render_assumptions_box,
)


def render_sip_calculator_widget(macro_context: Optional[Dict[str, Any]] = None):
    col1, col2, col3 = st.columns(3)
    with col1:
        sip_amount = st.slider(
            "Monthly SIP (₹)", min_value=1000, max_value=200000, value=10000, step=1000
        )
    with col2:
        return_rate = st.slider(
            "Expected Return (%)", min_value=5, max_value=25, value=13, step=1
        )
    with col3:
        years = st.slider(
            "Duration (Years)", min_value=1, max_value=40, value=10, step=1
        )

    fv = calculate_sip_future_value(sip_amount, return_rate / 100.0, years)
    invested = sip_amount * 12 * years
    wealth_gained = fv - invested

    st.markdown("<br>", unsafe_allow_html=True)
    res1, res2, res3 = st.columns(3)
    with res1:
        st.metric("Total Invested", f"₹{invested:,.0f}")
    with res2:
        st.metric("Wealth Gained", f"₹{wealth_gained:,.0f}")
    with res3:
        st.metric("Total Future Value", f"₹{fv:,.0f}")

    macro_context = macro_context or get_macro_context()
    inflation_meta = macro_context.get(
        "inflation",
        {
            "value": macro_context.get("inflation_rate", 0.06),
            "source": "fallback",
        },
    )
    assumptions = build_projection_assumptions(
        inflation_rate=float(inflation_meta.get("value", 0.06)),
        inflation_source=str(inflation_meta.get("source", "Fallback macro context")),
        roi=return_rate / 100.0,
        roi_basis="Interactive SIP calculator return assumption",
        sip_topup_rate=0.10,
    )

    st.markdown("#### SIP Projection Timeline")
    render_assumptions_box(assumptions)
    st.dataframe(
        build_projection_timeline_table(
            initial_investment=0.0,
            monthly_sip=float(sip_amount),
            annual_return_rate=return_rate / 100.0,
            years=int(years),
        ),
        use_container_width=True,
        hide_index=True,
    )
