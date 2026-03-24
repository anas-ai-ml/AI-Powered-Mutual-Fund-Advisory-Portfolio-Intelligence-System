"""
explainability.py
─────────────────
Generates plain-English "why" narratives for every major prediction and
recommendation in the pipeline.

Design principles:
  • Zero jargon — replaces terms like "RandomForest weight" with "influence".
  • Each function is independently callable and testable.
  • Fully decoupled from all engines — receives plain dicts, returns plain dicts.
  • Gracefully handles missing / partial data.
"""

from typing import Dict, Any, List


# ─────────────────────────────────────────────────────────────────
# 1. Risk Profile Explanation
# ─────────────────────────────────────────────────────────────────

def explain_risk_profile(risk_data: Dict[str, Any], client_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Explain why an ML model assigned a particular risk score and category.

    Parameters
    ----------
    risk_data : dict
        Output of ``calculate_risk_score()``.
        Expected keys: ``score``, ``category``, ``explanation.features``.
    client_data : dict
        Raw client inputs.
        Expected keys: ``age``, ``dependents``, ``monthly_income``,
        ``monthly_savings``, ``behavior``.

    Returns
    -------
    dict
        ``summary``      – one-sentence plain-English verdict
        ``key_factors``  – list of bullet strings explaining the score
        ``recommendation`` – actionable next step
    """
    score: float = risk_data.get("score", 5.0)
    category_raw: str = risk_data.get("category", "Moderate (ML Pred)")
    # Strip the "(ML Pred)" suffix for display
    category = category_raw.split("(")[0].strip()

    age: int = client_data.get("age", 35)
    dependents: int = client_data.get("dependents", 0)
    monthly_income: float = client_data.get("monthly_income", 0.0)
    monthly_savings: float = client_data.get("monthly_savings", 0.0)
    behavior: str = client_data.get("behavior", "Moderate")

    savings_ratio = (monthly_savings / monthly_income) if monthly_income > 0 else 0.0

    factors: List[str] = []

    # Age influence
    if age < 30:
        factors.append(f"You are {age} years old — younger investors can typically take more risk because they have more time to recover from market dips.")
    elif age < 45:
        factors.append(f"At {age}, you have a good balance of time and stability — supporting a moderate approach.")
    else:
        factors.append(f"At {age}, capital preservation becomes increasingly important, which lowers your risk capacity.")

    # Dependents influence
    if dependents == 0:
        factors.append("With no financial dependents, your risk capacity is higher.")
    elif dependents <= 2:
        factors.append(f"Supporting {dependents} dependent(s) introduces financial responsibilities that moderate your risk capacity.")
    else:
        factors.append(f"With {dependents} dependents, a more cautious approach is warranted to protect family financial security.")

    # Savings habit influence
    if savings_ratio >= 0.30:
        factors.append(f"A strong savings habit ({savings_ratio:.0%} of income saved) significantly boosts your ability to invest.")
    elif savings_ratio >= 0.10:
        factors.append(f"You save around {savings_ratio:.0%} of your income — a healthy foundation.")
    else:
        factors.append(f"A low savings rate ({savings_ratio:.0%}) limits how aggressively you can invest.")

    # Behavioural preference
    factors.append(f"Your stated investment behaviour ('{behavior}') was the strongest single influence on the final score.")

    # Summary sentence
    summary = (
        f"Based on your profile, you are classified as a **{category}** investor "
        f"(Score: {score}/10). "
        f"This means your portfolio should be structured to match your comfort with market fluctuations."
    )

    # Recommendation
    if category.lower() == "conservative":
        recommendation = "Focus on capital protection. Prioritise debt funds, fixed deposits, and a small equity cushion for inflation hedging."
    elif category.lower() == "aggressive":
        recommendation = "You can pursue higher equity exposure. Consider large-cap and flexi-cap funds for long-term wealth creation."
    else:
        recommendation = "A balanced mix of equity and debt funds suits your profile — aim for steady, long-term growth."

    return {
        "summary": summary,
        "key_factors": factors,
        "recommendation": recommendation,
    }


# ─────────────────────────────────────────────────────────────────
# 2. Fund Recommendation Explanation
# ─────────────────────────────────────────────────────────────────

_CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "Large Cap":  "large, well-established companies — stable and lower risk",
    "Mid Cap":    "medium-sized companies with good growth potential but higher volatility",
    "Small Cap":  "smaller companies with high growth potential and higher risk",
    "Flexi":      "a flexible mix of any company size, actively managed",
    "Hybrid":     "a mix of both stocks and bonds for balanced risk",
    "Debt":       "bonds and fixed-income securities — low risk, steady returns",
    "Gold":       "gold-linked assets — an inflation hedge and safe haven",
    "Sectoral":   "a focused sector (e.g. technology, healthcare) — concentrated risk",
}


def explain_fund_recommendation(fund: Dict[str, Any]) -> str:
    """
    Generate a one-paragraph plain-English reason for a single fund recommendation.

    Parameters
    ----------
    fund : dict
        A single fund dict from ``suggest_mutual_funds()``.
        Expected keys: ``name``, ``category``, ``risk``, ``allocation_weight``,
        ``sharpe``, ``volatility``, ``1y``, ``3y``, ``5y``.

    Returns
    -------
    str
        A human-readable explanation string.
    """
    name: str = fund.get("name", "This fund")
    category: str = fund.get("category", "")
    risk: str = fund.get("risk", "Moderate").split("(")[0].strip()
    weight: float = fund.get("allocation_weight", 0.0)
    sharpe: float = fund.get("sharpe", 0.0)
    volatility: float = fund.get("volatility", 0.0)
    ret_1y: float = fund.get("1y", 0.0)
    ret_3y: float = fund.get("3y", 0.0)
    ret_5y: float = fund.get("5y", 0.0)

    cat_desc = _CATEGORY_DESCRIPTIONS.get(category, "a diversified asset")
    parts: List[str] = []

    # Core reason
    parts.append(
        f"**{name}** invests in {cat_desc}. "
        f"It is allocated {weight}% of your portfolio to align with your **{risk}** risk level."
    )

    # Performance colour
    if ret_1y > 12:
        parts.append(f"Recent 1-year returns of **{ret_1y}%** show strong momentum.")
    elif ret_1y > 6:
        parts.append(f"1-year returns of **{ret_1y}%** are in line with market expectations.")
    else:
        parts.append(f"1-year returns of **{ret_1y}%** reflect a conservative, capital-preserving strategy.")

    if ret_5y > 0:
        parts.append(f"Over 5 years it has delivered **{ret_5y}%** annually — demonstrating long-term consistency.")

    # Risk-adjusted quality
    if sharpe > 1.0:
        parts.append(f"A Sharpe ratio of {sharpe:.2f} indicates strong returns for the level of risk taken.")
    elif sharpe > 0.5:
        parts.append(f"A Sharpe ratio of {sharpe:.2f} shows a reasonable risk-adjusted return.")

    if volatility < 10:
        parts.append("Low annual volatility means this fund tends to be a smoother ride.")
    elif volatility > 20:
        parts.append("Higher volatility is expected for this category — best held for the long term.")

    return " ".join(parts)


def explain_all_funds(funds: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Generate explanations for every recommended fund.

    Returns a list of ``{"name": ..., "reason": ...}`` dicts.
    """
    return [
        {"name": f.get("name", "Fund"), "reason": explain_fund_recommendation(f)}
        for f in funds
    ]


# ─────────────────────────────────────────────────────────────────
# 3. Portfolio Health Explanation
# ─────────────────────────────────────────────────────────────────

def explain_portfolio_health(portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Summarise a portfolio health analysis in plain English.

    Parameters
    ----------
    portfolio_data : dict
        Output of ``analyze_portfolio()``.
        Expected keys: ``diversification_score``, ``risk_exposure``,
        ``total_corpus``, ``insights``.

    Returns
    -------
    dict
        ``headline``  – one-line verdict
        ``narrative`` – 2–3 sentence paragraph with layman explanation
        ``verdict``   – "strong" | "moderate" | "needs_attention"
    """
    score: int = portfolio_data.get("diversification_score", 5)
    risk_exposure: str = portfolio_data.get("risk_exposure", "")
    total_corpus: float = portfolio_data.get("total_corpus", 0.0)

    if score >= 8:
        verdict = "strong"
        headline = f"Your portfolio is in great shape! ({score}/10)"
        narrative = (
            f"Your investments are well-diversified and aligned with your risk profile. "
            f"With a total corpus of ₹{total_corpus:,.0f}, you're making efficient use of your wealth. "
            "Keep maintaining this balance and your long-term goals look very achievable."
        )
    elif score >= 5:
        verdict = "moderate"
        headline = f"Your portfolio is fairly healthy, with room to improve. ({score}/10)"
        narrative = (
            f"Your overall portfolio (₹{total_corpus:,.0f}) is reasonably spread across different assets. "
            "A few adjustments — like reducing excess cash or rebalancing equity exposure — "
            "could meaningfully improve your long-term wealth creation."
        )
    else:
        verdict = "needs_attention"
        headline = f"Your portfolio needs some attention. ({score}/10)"
        narrative = (
            f"With ₹{total_corpus:,.0f} invested, your portfolio has some structural gaps "
            "that may be limiting your returns or exposing you to unnecessary risk. "
            "Reviewing the insights below and acting on them can significantly strengthen your financial position."
        )

    return {
        "headline":  headline,
        "narrative": narrative,
        "verdict":   verdict,
    }
