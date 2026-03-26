from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from backend.engines.projection_engine import generate_projection_table


def render_assumptions_box(assumptions: Dict[str, Any], title: str = "Assumptions Used"):
    scenario_text = ", ".join(
        f"{name.title()}: {value}"
        for name, value in assumptions.get("base_return_scenarios", {}).items()
    )
    st.markdown(
        f"""
        <div style="border:1px solid #334155;background:#0f172a;padding:14px 16px;border-radius:10px;margin:10px 0 14px 0;">
            <div style="color:#f8fafc;font-weight:600;margin-bottom:8px;">{title}</div>
            <div style="color:#cbd5e1;line-height:1.6;">
                <div><strong>Inflation Rate:</strong> {assumptions.get("inflation_rate", "-")}</div>
                <div><strong>Expected ROI:</strong> {assumptions.get("expected_roi", "-")}</div>
                <div><strong>Base Return Scenarios:</strong> {scenario_text or "-"}</div>
                <div><strong>SIP Top-up Rate:</strong> {assumptions.get("sip_topup_rate", "-")}</div>
                <div><strong>Tax Treatment:</strong> {assumptions.get("tax_treatment", "-")}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_projection_timeline_table(
    initial_investment: float,
    monthly_sip: float,
    annual_return_rate: float,
    years: int,
) -> pd.DataFrame:
    df = generate_projection_table(
        initial_investment=initial_investment,
        monthly_sip=monthly_sip,
        annual_return_rate=annual_return_rate,
        years=years,
    )
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Year",
                "Cumulative Invested Amount",
                "Projected Value",
                "Wealth Created",
            ]
        )

    return pd.DataFrame(
        {
            "Year": df["year"].astype(int),
            "Cumulative Invested Amount": df["invested"].map(lambda value: f"₹{value:,.0f}"),
            "Projected Value": df["total_value"].map(lambda value: f"₹{value:,.0f}"),
            "Wealth Created": df["returns"].map(lambda value: f"₹{value:,.0f}"),
        }
    )


def build_goal_horizon_table(scenarios: List[Dict[str, Any]]) -> pd.DataFrame:
    if not scenarios:
        return pd.DataFrame(
            columns=[
                "Market Scenario",
                "Return Assumption",
                "Projected Corpus",
                "Inflation-Adjusted Corpus",
                "Probability of Achieving Goal",
            ]
        )

    def _format_probability(value: Any) -> str:
        if value is None:
            return "N/A"
        return f"{float(value):.1f}%"

    return pd.DataFrame(
        {
            "Market Scenario": [scenario.get("scenario", "-") for scenario in scenarios],
            "Return Assumption": [
                scenario.get("return_assumption", scenario.get("annual_return", "-"))
                for scenario in scenarios
            ],
            "Projected Corpus": [
                f"₹{float(scenario.get('final_corpus', 0.0)):,.0f}" for scenario in scenarios
            ],
            "Inflation-Adjusted Corpus": [
                f"₹{float(scenario.get('inflation_adjusted_corpus', 0.0)):,.0f}"
                for scenario in scenarios
            ],
            "Probability of Achieving Goal": [
                _format_probability(scenario.get("probability")) for scenario in scenarios
            ],
        }
    )


def build_step_up_comparison_table(sip_comparison: Dict[str, Any]) -> pd.DataFrame:
    if not sip_comparison:
        return pd.DataFrame(
            columns=[
                "Mode",
                "Monthly SIP (Year 1)",
                "Corpus at Goal",
                "Total Invested",
                "Wealth Multiplier",
            ]
        )

    rows = [sip_comparison.get("flat", {}), sip_comparison.get("step_up", {})]
    return pd.DataFrame(
        {
            "Mode": [row.get("mode", "-") for row in rows],
            "Monthly SIP (Year 1)": [
                f"₹{float(row.get('monthly_sip_year_1', 0.0)):,.0f}" for row in rows
            ],
            "Corpus at Goal": [
                f"₹{float(row.get('corpus_at_goal', 0.0)):,.0f}" for row in rows
            ],
            "Total Invested": [
                f"₹{float(row.get('total_invested', 0.0)):,.0f}" for row in rows
            ],
            "Wealth Multiplier": [
                f"{float(row.get('wealth_multiplier', 0.0)):.2f}x" for row in rows
            ],
        }
    )
