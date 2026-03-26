from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from backend.engines.explanation_standards import get_score_reasoning


# Display-only: ideal ranges derived from age + dependents + income bracket.
# Intentionally lives in this UI component (not the scoring engine).
IDEAL_RISK_RANGE_BY_PROFILE: Dict[str, Tuple[float, float]] = {
    # Key format: "{age_band}|{dependents_band}|{income_band}"
    "young|none|high": (8.0, 10.0),
    "young|none|mid": (7.5, 9.5),
    "young|none|low": (7.0, 9.0),

    "young|some|high": (7.5, 9.0),
    "young|some|mid": (7.0, 8.5),
    "young|some|low": (6.5, 8.0),

    "young|many|high": (7.0, 8.5),
    "young|many|mid": (6.5, 8.0),
    "young|many|low": (6.0, 7.5),

    "mid|none|high": (7.0, 9.0),
    "mid|none|mid": (6.5, 8.5),
    "mid|none|low": (6.0, 8.0),

    "mid|some|high": (6.5, 8.0),
    "mid|some|mid": (6.0, 7.5),
    "mid|some|low": (5.5, 7.0),

    "mid|many|high": (6.0, 7.5),
    "mid|many|mid": (5.5, 7.0),
    "mid|many|low": (5.0, 6.5),

    # Example requirement:
    # "A 45-year-old with no dependents and Rs 1.5L income should ideally score 6.5-7.5."
    "older|none|high": (6.5, 7.5),
    "older|none|mid": (6.0, 7.2),
    "older|none|low": (5.5, 6.8),

    "older|some|high": (6.0, 7.2),
    "older|some|mid": (5.5, 6.8),
    "older|some|low": (5.0, 6.5),

    "older|many|high": (5.5, 6.8),
    "older|many|mid": (5.0, 6.5),
    "older|many|low": (4.5, 6.0),
}


def _income_band(monthly_income: float) -> str:
    # Assumes monthly income is in INR.
    if monthly_income >= 150000:
        return "high"
    if monthly_income >= 50000:
        return "mid"
    return "low"


def _age_band(age: int) -> str:
    if age < 30:
        return "young"
    if age < 45:
        return "mid"
    return "older"


def _dependents_band(dependents: int) -> str:
    if dependents <= 0:
        return "none"
    if dependents <= 2:
        return "some"
    return "many"


def ideal_risk_range_for_profile(
    age: int, dependents: int, monthly_income: float
) -> Tuple[float, float]:
    key = f"{_age_band(age)}|{_dependents_band(dependents)}|{_income_band(monthly_income)}"
    return IDEAL_RISK_RANGE_BY_PROFILE.get(key, (6.0, 8.0))


def _status_from_score_and_target(
    your_score: float, ideal_target: float, lower_is_better: bool = False
) -> Tuple[str, str]:
    """
    Returns (status_icon, status_label) using +/- 15% tolerance on ideal_target.
    """
    if lower_is_better:
        # Not used for current 5-score panel but kept for completeness.
        raise NotImplementedError

    if your_score >= ideal_target:
        return "✅", "On Track"

    # "within 15% below ideal"
    if your_score >= ideal_target * 0.85:
        return "⚠️", "Attention"
    return "❌", "Action Required"


def _status_from_score_in_range(
    your_score: float, ideal_range: Tuple[float, float]
) -> Tuple[str, str]:
    lo, hi = ideal_range
    if lo <= your_score <= hi:
        return "✅", "On Track"
    # attention if within 15% below the lower bound of the ideal range
    if your_score >= lo * 0.85:
        return "⚠️", "Attention"
    return "❌", "Action Required"


def _normalize_0_10(value: Any) -> Optional[float]:
    """
    Converts diversification-like score into a 0-10 scale.
    Accepts either a plain float (0-10) or a dict with score-like keys.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 10.0:
        return v
    # Assume 0-100
    return v / 10.0


def render_score_intelligence_panel(
    *,
    client_data: Dict[str, Any],
    risk_profile: Dict[str, Any],
    diversification: Any,
    macro_context: Dict[str, Any],
    ai_recommended_funds: List[Dict[str, Any]],
    goal_confidence_probability: Optional[float],
    goal_fix_recommendation: Optional[Dict[str, Any]] = None,
    goal_last_updated: str = "unknown",
):
    st.markdown("---")
    st.subheader("What Do Your Scores Mean? - Benchmarks & Reasoning")

    age = int(client_data.get("age", 0))
    dependents = int(client_data.get("dependents", 0))
    monthly_income = float(client_data.get("monthly_income", client_data.get("income", 0.0)))

    # Card values
    risk_score = float(risk_profile.get("score", 0.0))
    ideal_range = ideal_risk_range_for_profile(age, dependents, monthly_income)
    risk_icon, risk_status = _status_from_score_in_range(risk_score, ideal_range)

    div_score_0_10 = _normalize_0_10(
        diversification.get("diversification_score")
        if isinstance(diversification, dict)
        else diversification
    )
    if div_score_0_10 is None:
        div_score_0_10 = 0.0
    div_icon, div_status = _status_from_score_and_target(div_score_0_10, 9.0)

    div_penalty_detail = None
    if isinstance(diversification, dict):
        if diversification.get("penalties"):
            penalties = diversification.get("penalties")
            if isinstance(penalties, list) and penalties:
                div_penalty_detail = str(penalties[0])
        elif diversification.get("violations"):
            violations = diversification.get("violations")
            if isinstance(violations, list) and violations:
                div_penalty_detail = str(violations[0])
        elif diversification.get("penalty") is not None:
            try:
                p = float(diversification.get("penalty"))
                if p > 0:
                    div_penalty_detail = f"Primary penalty magnitude: {p:.2f}"
            except (TypeError, ValueError):
                pass

    stability_score = float(macro_context.get("macro_context_score", 1.0)) * 100.0
    stability_icon, stability_status = _status_from_score_and_target(stability_score, 80.0)

    ai_scores = []
    for f in ai_recommended_funds or []:
        s = f.get("ai_score", f.get("score", None))
        if s is not None:
            try:
                ai_scores.append(float(s))
            except (TypeError, ValueError):
                continue
    ai_above_85 = sum(1 for s in ai_scores if s >= 85.0)
    ai_total = len(ai_scores)
    ai_above_pct = (ai_above_85 / ai_total) * 100.0 if ai_total > 0 else 0.0
    ai_icon, ai_status = _status_from_score_and_target(ai_above_pct, 85.0)

    if goal_confidence_probability is None:
        confidence_score = None
        goal_icon, goal_status = "ℹ️", "Set a goal to see your confidence score"
    else:
        confidence_score = float(goal_confidence_probability)
        goal_icon, goal_status = _status_from_score_and_target(confidence_score, 85.0)

    # Row 1: Risk, Diversification, AI Market
    r1 = st.columns(3)
    with r1[0]:
        st.markdown(f"**Risk Score**  {risk_score:.1f}/10")
        st.markdown(f"**Target:** Profile-specific | **Status:** {risk_icon} {risk_status}")
        st.markdown(f"**Your Gap:** Score {risk_score:.1f} vs Ideal {ideal_range[0]:.1f}-{ideal_range[1]:.1f}")
        
        with st.expander("Show Methodology Deep-Dive", expanded=False):
            st.markdown("**Why this target?**")
            st.markdown("A 45-year-old with no dependents and ₹1.5L income should ideally score 6.5-7.5. Risk capacity shrinks as retirement approaches.")
            st.markdown("**Mathematical Basis:** Predicted by Random Forest using 4 weighted factors: Behavior (35%), Savings Ratio (25%), Age (25%), Dependents (15%).")
            st.markdown("**Geopolitical Factor:** During RBI rate hike cycles, even Aggressive profiles should dial down by 0.5-1.0 points due to elevated EMI burden.")

    with r1[1]:
        st.markdown(f"**Diversification Score**  {div_score_0_10:.1f}/10")
        st.markdown(f"**Target:** 9.0/10 | **Status:** {div_icon} {div_status}")
        st.markdown(f"**Your Gap:** {max(0.0, 10.0 - div_score_0_10):.1f} points of efficiency left on the table.")
        if div_penalty_detail:
            st.markdown(f"**Penalty Drag:** {div_penalty_detail}")

        with st.expander("Show Methodology Deep-Dive", expanded=False):
            st.markdown("**Why this target?** 9.0 is the institutional gold standard - it means capital is deployed efficiently across Equity, Debt, and Gold.")
            st.markdown("**Mathematical Basis:** Score starts at 10.0 and applies penalties for Cash Drag, Risk Mismatch, and Over-Concentration.")
            st.markdown("**Geopolitical Factor:** During periods of high global uncertainty (VIX > 25), a slightly lower score (7.5-8.5) is acceptable if defensive.")

    with r1[2]:
        st.markdown(f"**AI Market Score**  {ai_above_pct:.0f}/100")
        st.markdown(f"**Target:** 85/100 | **Status:** {ai_icon} {ai_status}")
        if ai_total > 0:
            st.markdown(f"**Your Gap:** {ai_above_85}/{ai_total} funds meet target.")
        else:
            st.markdown("**Your Gap:** No funds recommended yet.")

        with st.expander("Show Methodology Deep-Dive", expanded=False):
            st.markdown("**Why this target?** 85+ means a fund is both a strong performer AND the right tool for current market conditions.")
            st.markdown("**Mathematical Basis:** AI Score = (30% × 1Y Return) + (30% × 3Y Return) + (20% × Consistency) + (20% × Market-Fit Bonus).")
            st.markdown("**Geopolitical Factor:** Market-Fit Bonus is dynamic - Bearish or High VIX environments boost defensive assets by +0.20.")

    # Row 2: Market Stability, Goal Confidence
    r2 = st.columns(2)
    with r2[0]:
        st.markdown(f"**Market Stability**  {stability_score:.0f}%")
        st.markdown(f"**Target:** >80% | **Status:** {stability_icon} {stability_status}")
        st.progress(min(max(stability_score / 100.0, 0.0), 1.0))
        st.caption(f"Refreshed: `{goal_last_updated}`")

        with st.expander("Show Methodology Deep-Dive", expanded=False):
            st.markdown("**Why this target?** > 80% is the 'Green Light' - it means inflation and volatility are within comfort bands.")
            st.markdown("**Mathematical Basis:** Stability = 1 − Composite Risk. Risk = (35% × Inflation) + (35% × Geopolitical) + (30% × VIX).")
            st.markdown("**Geopolitical Factor:** Live inputs from RBI repo rate decisions, India CPI print, and CBOE VIX.")

    with r2[1]:
        show_fix = (goal_fix_recommendation is not None and confidence_score is not None and confidence_score < 50.0)
        if show_fix:
            st.markdown("**Goal Confidence**  Low (<50%)")
        else:
            st.markdown(f"**Goal Confidence**  {f'{confidence_score:.0f}%' if confidence_score is not None else 'N/A'}")
        st.markdown(f"**Target:** 85% | **Status:** {goal_icon} {goal_status}")

        if confidence_score is None:
            st.caption("Set a goal to see your confidence score.")
        elif show_fix and goal_fix_recommendation:
            gap_analysis = goal_fix_recommendation.get("gap_analysis", "")
            st.markdown(f"**Gap:** {gap_analysis}")
        else:
            gap_points = max(0.0, 85.0 - (confidence_score or 0.0))
            if (confidence_score or 0.0) >= 85:
                st.markdown("**Gap:** Plan on track. Maintain SIP.")
            else:
                st.markdown(f"**Gap:** {gap_points:.0f}% below target.")

        with st.expander("Show Methodology Deep-Dive", expanded=False):
            st.markdown("**Why this target?** 85% means your plan succeeds in 850 out of 1,000 simulations including bad years and inflation spikes.")
            st.markdown("**Mathematical Basis:** Final Confidence = Base Monte Carlo Probability × Macro Stability Score.")
            st.markdown("**Geopolitical Factor:** A geopolitical shock can drop Macro Stability, reducing confidence even if market returns are stable.")
            if show_fix and goal_fix_recommendation:
                recommended = goal_fix_recommendation.get("recommended", "")
                st.markdown("---")
                st.markdown(f"**Recommended path:** {recommended.replace('_', ' ').title()}")
                st.markdown("**Recovery Options:**")
                st.markdown(f"- {goal_fix_recommendation.get('option_1', '')}")
                st.markdown(f"- {goal_fix_recommendation.get('option_2', '')}")
                st.markdown(f"- {goal_fix_recommendation.get('option_3', '')}")

    # Power-user standards reference at the bottom
    with st.expander("ℹ️ How are these targets set? (Deep Dive)", expanded=False):
        standards = [
            get_score_reasoning("Risk Score"),
            get_score_reasoning("Diversification Score"),
            get_score_reasoning("AI Market Score"),
            get_score_reasoning("Market Stability Score"),
            get_score_reasoning("Goal Confidence Band"),
        ]
        for s in standards:
            st.markdown(f"### {s.score_name}")
            st.markdown(f"- Scale: `{s.scale}`")
            st.markdown(f"- Mathematical Basis: {s.mathematical_basis}")
            st.markdown(f"- Geopolitical Factor: {s.geopolitical_basis}")
            st.markdown(f"- Historical Calibration: {s.historical_calibration}")
            st.markdown(f"- User-Facing Summary: {s.user_facing_summary}")
