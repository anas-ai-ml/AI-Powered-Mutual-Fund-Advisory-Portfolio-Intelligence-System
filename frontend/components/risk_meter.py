import plotly.graph_objects as go
import streamlit as st

from backend.scoring.calibration_engine import RISK_BAND_THRESHOLDS


def render_risk_meter(score: float):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Risk Score", "font": {"size": 24, "color": "white"}},
            gauge={
                "axis": {"range": [None, 10], "tickwidth": 1, "tickcolor": "white"},
                "bar": {"color": "#4facfe"},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {
                        "range": [
                            RISK_BAND_THRESHOLDS["Conservative"]["min"],
                            RISK_BAND_THRESHOLDS["Conservative"]["max"],
                        ],
                        "color": "rgba(0, 255, 128, 0.3)",
                    },
                    {
                        "range": [
                            RISK_BAND_THRESHOLDS["Moderate"]["min"],
                            RISK_BAND_THRESHOLDS["Moderate"]["max"],
                        ],
                        "color": "rgba(255, 204, 0, 0.3)",
                    },
                    {
                        "range": [
                            RISK_BAND_THRESHOLDS["Aggressive"]["min"],
                            RISK_BAND_THRESHOLDS["Aggressive"]["max"],
                        ],
                        "color": "rgba(255, 51, 102, 0.3)",
                    },
                ],
            },
        )
    )

    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    st.plotly_chart(fig, width="stretch")


def render_risk_score_card(risk_output: dict):
    """
    Streamlit UI for the Risk Score:
      - Score gauge
      - Band table (3 rows)
      - Horizontal contribution breakdown chart
    """
    score = float(risk_output.get("score", 0.0))
    category = str(risk_output.get("category", ""))
    factors = risk_output.get("factors", [])

    # 1) Gauge
    render_risk_meter(score)

    # 2) Band table (always visible)
    why_by_band = {
        "Conservative": "Built for capital preservation; helps limit drawdowns and volatility risk.",
        "Moderate": "A balanced growth approach; aims for steady returns while keeping risk controlled.",
        "Aggressive": "Maximizes long-term growth potential; expects higher volatility and drawdown swings.",
    }

    rows = []
    for band in ["Conservative", "Moderate", "Aggressive"]:
        bounds = RISK_BAND_THRESHOLDS.get(band, {"min": "", "max": ""})
        is_your_band = "✅" if category == band else ""
        rows.append(
            {
                "Your Band": f"{is_your_band} {band}".strip(),
                "Threshold": f"{bounds['min']} - {bounds['max']}",
                "Why This Matters": why_by_band.get(band, ""),
            }
        )

    st.caption("Risk Band Benchmarks (transparent thresholds)")
    st.table(rows)

    # 3) Factor contribution breakdown
    # contributions are in "risk-score points"; convert to % for a consistent UX scale.
    contribs = []
    rationales = {}
    for f in factors:
        name = f.get("name", "Factor")
        contrib = float(f.get("contribution", 0.0))
        contribs.append(contrib)
        rationales[name] = f.get("rationale", "")

    total_contrib = sum(contribs) if contribs else 0.0
    if total_contrib <= 0:
        contrib_perc = [0.0 for _ in contribs]
    else:
        contrib_perc = [(c / total_contrib) * 100.0 for c in contribs]

    y_labels = [f.get("name", "Factor") for f in factors] if factors else []
    fig = go.Figure(
        go.Bar(
            x=contrib_perc,
            y=y_labels,
            orientation="h",
            marker={"color": "#4facfe"},
            customdata=[rationales.get(n, "") for n in y_labels],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Contribution: %{x:.1f}% of score<br>"
                "%{customdata}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
        xaxis_title="Contribution to your risk score (%)",
        yaxis_title="Factor",
    )
    st.markdown("#### What influenced your score most?")
    st.plotly_chart(fig, width="stretch")
