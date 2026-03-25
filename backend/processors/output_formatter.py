"""
output_formatter.py
───────────────────
Transforms structured engine output into user-friendly, multi-level formats.

Three output levels:
  LEVEL 1 — SIMPLE:   Plain English, 1–2 sentences. For layman users.
  LEVEL 2 — DETAILED: Key numbers + context narrative. For semi-technical users.
  LEVEL 3 — RAW:      Original engine output, unchanged.

Additional outputs:
  • Insight Cards  — Trend / Risk / Recommendation with colour coding
  • Confidence Band — High / Medium / Low bucket for any confidence score
  • Disclaimer      — Standard advisory disclaimer text
  • Scenarios       — Best / Expected / Worst corpus projections
"""

from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

DISCLAIMER = (
    "Predictions are based on current available data and may change as market "
    "conditions evolve. This is not financial advice. Past performance is not "
    "indicative of future results. Please consult a SEBI-registered financial "
    "advisor before making investment decisions."
)

_CONFIDENCE_BANDS = [
    (0.80, "High", "green", "[OK]"),
    (0.50, "Medium", "yellow", "[!]"),
    (0.00, "Low", "red", "[!!]"),
]

_RISK_COLOUR: Dict[str, str] = {
    "conservative": "green",
    "moderate": "yellow",
    "aggressive": "red",
}

_MC_COLOUR: Dict[str, str] = {
    "high": "green",
    "medium": "yellow",
    "low": "red",
}


# ─────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────


def get_confidence_band(confidence: float) -> Dict[str, str]:
    """
    Map a raw confidence value [0, 1] to a named confidence band.

    Returns
    -------
    dict
        ``label``  – "High" | "Medium" | "Low"
        ``colour`` – "green" | "yellow" | "red"
        ``icon``   – emoji indicator
        ``pct``    – formatted percentage string (e.g. "87%")
    """
    confidence = max(0.0, min(1.0, confidence))
    for threshold, label, colour, icon in _CONFIDENCE_BANDS:
        if confidence >= threshold:
            return {
                "label": label,
                "colour": colour,
                "icon": icon,
                "pct": f"{confidence:.0%}",
            }
    # Fallback (should never reach here)
    return {"label": "Low", "colour": "red", "icon": "[!!]", "pct": f"{confidence:.0%}"}


def get_disclaimer() -> str:
    """Return the standard investment disclaimer string."""
    return DISCLAIMER


# ─────────────────────────────────────────────────────────────────
# LEVEL 1 & 2: Natural Language Summaries
# ─────────────────────────────────────────────────────────────────


def format_risk_summary(risk_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Format the risk profile output at SIMPLE and DETAILED levels.

    Parameters
    ----------
    risk_data : dict
        Output of ``calculate_risk_score()``.
        Expected keys: ``score``, ``category``.

    Returns
    -------
    dict
        ``simple``   – one-sentence layman summary
        ``detailed`` – numerical detail with interpretation
        ``raw``      – original risk_data dict reference (unchanged)
    """
    score: float = risk_data.get("score", 5.0)
    category_raw: str = risk_data.get("category", "Moderate (ML Pred)")
    category = category_raw.split("(")[0].strip()

    if category.lower() == "conservative":
        simple = (
            "Your investment style prefers safety over high returns. "
            "Think of it like keeping your money in a safe, steady bank rather than gambling on the stock market."
        )
    elif category.lower() == "aggressive":
        simple = (
            "You are comfortable with market ups and downs in exchange for potentially higher long-term returns. "
            "Your portfolio can handle more risk."
        )
    else:
        simple = (
            "You prefer a balanced approach — some safety, some growth. "
            "Your portfolio will be split between stable and growth-oriented investments."
        )

    detailed = (
        f"Risk Category: **{category}** | ML Risk Score: **{score}/10**. "
        f"A score of {score:.1f} places you in the {category.lower()} segment. "
        "This score is calculated using your age, number of dependents, "
        "savings rate, and stated investment behaviour."
    )

    return {"simple": simple, "detailed": detailed, "raw": risk_data}


def format_macro_summary(macro_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Format the macro context engine output at SIMPLE and DETAILED levels.

    Parameters
    ----------
    macro_context : dict
        Output of ``get_macro_context()``.

    Returns
    -------
    dict
        ``simple``   – plain-English market snapshot
        ``detailed`` – key numbers and drivers
        ``raw``      – original macro_context dict reference (unchanged)
    """
    score: float = macro_context.get("macro_context_score", 1.0)
    inflation: float = macro_context.get("inflation_rate", 0.06)
    int_rate: float = macro_context.get("interest_rate", 0.065)
    int_trend: str = macro_context.get("interest_rate_trend", "stable")
    adj_conf: float = macro_context.get("adjusted_confidence", 0.85)
    explanation: str = macro_context.get("explanation", "")

    if score >= 0.75:
        simple = (
            "The overall economic environment looks relatively calm and stable right now. "
            "Good conditions for steady, planned investing."
        )
    elif score >= 0.50:
        simple = (
            "There are some economic headwinds — like moderate inflation or global uncertainty — "
            "but conditions are manageable for long-term investors."
        )
    else:
        simple = (
            "The macro environment has notable challenges right now. "
            "It's a good time to be cautious and stick to your long-term plan rather than making impulsive changes."
        )

    detailed = (
        f"Macro Stability Score: **{score:.0%}** | "
        f"Inflation: **{inflation:.1%}** | "
        f"Policy Rate: **{int_rate:.2%}** ({int_trend}) | "
        f"Adjusted Prediction Confidence: **{adj_conf:.0%}**. "
        f"{explanation}"
    )

    return {"simple": simple, "detailed": detailed, "raw": macro_context}


def format_monte_carlo_summary(
    probability: float, macro_context: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Format the Monte Carlo probability at SIMPLE and DETAILED levels.

    Parameters
    ----------
    probability : float
        Success probability percentage (0–100).
    macro_context : dict, optional
        If provided, adjusted_confidence is factored into the narrative.

    Returns
    -------
    dict
        ``simple``   – one-sentence plain-English interpretation
        ``detailed`` – probability with macro adjustment note
        ``raw``      – ``{"probability": probability}``
    """
    adj = None
    if macro_context:
        adj = macro_context.get("adjusted_confidence")

    if probability > 80:
        simple = (
            f"Great news — there is a **{probability:.0f}%** chance you'll hit your financial target. "
            "You're on a very secure path."
        )
    elif probability > 50:
        simple = (
            f"There is a **{probability:.0f}%** chance of reaching your goal. "
            "A small increase in your monthly investment could push this above 80%."
        )
    else:
        simple = (
            f"A **{probability:.0f}%** chance of reaching your goal means your current plan "
            "may need adjusting. Consider increasing your SIP or extending your timeline."
        )

    adj_note = f" Macro-adjusted confidence: **{adj:.0%}**." if adj is not None else ""

    detailed = (
        f"Monte Carlo Simulation across 1,000 market scenarios: "
        f"**{probability:.0f}%** success probability.{adj_note} "
        "This test simulates different market conditions to estimate how likely your plan is to succeed."
    )

    return {"simple": simple, "detailed": detailed, "raw": {"probability": probability}}


# ─────────────────────────────────────────────────────────────────
# Insight Cards
# ─────────────────────────────────────────────────────────────────


def build_insight_cards(
    risk_data: Dict[str, Any],
    probability: float,
    portfolio_data: Dict[str, Any],
    macro_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Build a set of three Insight Cards for the dashboard UI.

    Each card contains a ``title``, ``value``, ``colour``, ``icon``,
    and ``recommendation`` suitable for Streamlit metric-style display.

    Parameters
    ----------
    risk_data : dict
        Output of ``calculate_risk_score()``.
    probability : float
        Monte Carlo success probability (0–100).
    portfolio_data : dict
        Output of ``analyze_portfolio()``.
    macro_context : dict, optional
        Output of ``get_macro_context()``.

    Returns
    -------
    List[dict]
        List of three insight card dicts.
    """
    cards: List[Dict[str, str]] = []

    # ── Card 1: Market Trend / Macro ─────────────────────
    macro_score = (
        macro_context.get("macro_context_score", 1.0) if macro_context else 1.0
    )
    int_trend = (
        macro_context.get("interest_rate_trend", "stable")
        if macro_context
        else "stable"
    )

    if macro_score >= 0.75:
        trend_val = "Stable"
        trend_colour = "green"
        trend_rec = "Good time to stay invested and maintain your SIP."
    elif macro_score >= 0.50:
        trend_val = "Cautious"
        trend_colour = "yellow"
        trend_rec = "Continue your plan but avoid large lump-sum investments right now."
    else:
        trend_val = "Uncertain"
        trend_colour = "red"
        trend_rec = "Hold your position. Avoid making reactive changes based on short-term news."

    cards.append(
        {
            "title": "Market Environment",
            "value": trend_val,
            "colour": trend_colour,
            "icon": "🌐",
            "recommendation": trend_rec,
        }
    )

    # ── Card 2: Risk Level ────────────────────────────────
    score: float = risk_data.get("score", 5.0)
    category_raw: str = risk_data.get("category", "Moderate (ML Pred)")
    category = category_raw.split("(")[0].strip()
    risk_colour = _RISK_COLOUR.get(category.lower(), "yellow")

    if category.lower() == "conservative":
        risk_rec = "Stay with debt funds and Fixed Deposits. Add small equity positions gradually."
    elif category.lower() == "aggressive":
        risk_rec = "Maximize equity through diversified funds. Consider SIP in Small & Mid Cap."
    else:
        risk_rec = (
            "Hold position. A 60/40 equity-to-debt mix is ideal for your profile."
        )

    cards.append(
        {
            "title": "Your Risk Level",
            "value": f"{category} ({score:.1f}/10)",
            "colour": risk_colour,
            "icon": "Risk",
            "recommendation": risk_rec,
        }
    )

    # ── Card 3: Goal Achievement ───────────────────────────
    mc_band = get_confidence_band(probability / 100.0)
    if probability > 80:
        goal_rec = "You're on track. Good time to invest. Keep your SIP running."
    elif probability > 50:
        goal_rec = (
            "Hold your position and consider a 10% SIP increase for extra security."
        )
    else:
        goal_rec = "Proceed with caution. A financial review is recommended."

    cards.append(
        {
            "title": "Goal Achievement",
            "value": f"{probability:.0f}% Probability",
            "colour": mc_band["colour"],
            "icon": "Goal",
            "recommendation": goal_rec,
        }
    )

    return cards


# ─────────────────────────────────────────────────────────────────
# Scenario Projections
# ─────────────────────────────────────────────────────────────────


def build_scenario_projections(
    existing_corpus: float,
    monthly_sip: float,
    years: int,
) -> List[Dict[str, Any]]:
    """
    Compute Best / Expected / Worst corpus projections using three return rates.

    Uses standard compound-growth formula with monthly compounding:
        FV = P × (1+r)^n + SIP × [((1+r)^n − 1) / r]
    where r = monthly rate and n = months.

    Parameters
    ----------
    existing_corpus : float
        Current total invested amount in INR.
    monthly_sip : float
        Monthly SIP contribution in INR.
    years : int
        Investment horizon in years.

    Returns
    -------
    List[dict]
        Three scenario dicts each with ``scenario``, ``annual_return``,
        ``final_corpus``, ``colour``, ``icon``.
    """
    scenarios = [
        ("Best Case", 0.15, "green", "[Best]"),
        ("Expected Case", 0.12, "yellow", "[Expected]"),
        ("Worst Case", 0.08, "red", "[Worst]"),
    ]

    results = []
    months = years * 12

    for name, annual_rate, colour, icon in scenarios:
        r = annual_rate / 12  # monthly rate
        if r == 0:
            fv = existing_corpus + monthly_sip * months
        else:
            fv = existing_corpus * ((1 + r) ** months) + monthly_sip * (
                ((1 + r) ** months - 1) / r
            )

        results.append(
            {
                "scenario": name,
                "annual_return": f"{annual_rate:.0%}",
                "final_corpus": round(fv, 0),
                "colour": colour,
                "icon": icon,
            }
        )

    return results
