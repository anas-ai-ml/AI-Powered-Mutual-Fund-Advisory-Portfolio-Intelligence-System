from typing import Any, Dict

from backend.funds.investment_mode import determine_market_regime


def recommend_investment_mode(
    investor_profile: Dict[str, Any], market_signals: Dict[str, Any]
) -> Dict[str, Any]:
    regime = determine_market_regime(market_signals)
    risk_score = float(investor_profile.get("risk_score", 5))
    horizon_years = int(investor_profile.get("horizon_years", 10))
    investment_amount = float(investor_profile.get("investment_amount", 0))
    liquidity_months = int(investor_profile.get("liquidity_months", 6))

    if regime == "VOLATILE":
        primary_mode = "SIP"
        rationale = "Volatile conditions favor staggered deployment and liquidity protection."
        allocation = {"sip": 100, "lumpsum": 0}
    elif regime == "BEARISH":
        primary_mode = "STP"
        rationale = "Bearish conditions favor phased transfer from low-volatility assets."
        allocation = {"debt_to_equity": 100, "duration_months": 12}
    elif regime == "BULLISH" and horizon_years >= 5 and risk_score >= 7:
        primary_mode = "LUMPSUM+SIP"
        rationale = "Long horizon and high risk capacity support faster market entry with ongoing averaging."
        allocation = {"lumpsum": 60, "sip": 40}
    else:
        primary_mode = "SIP"
        rationale = "Systematic investing is the default for mixed or uncertain conditions."
        allocation = {"sip": 100}

    strategy = {
        "title": primary_mode,
        "primary_mode": primary_mode,
        "regime": regime,
        "rationale": rationale,
        "allocation": allocation,
        "investment_amount": investment_amount,
        "liquidity_months": liquidity_months,
        "description": (
            f"{primary_mode} is recommended for a {regime.lower()} market regime "
            f"with a {horizon_years}-year horizon."
        ),
    }

    sip_pct = allocation.get("sip", 0)
    lumpsum_pct = allocation.get("lumpsum", 0)
    if investment_amount > 0 and sip_pct:
        strategy["monthly_sip"] = round(investment_amount * sip_pct / 100, 2)
    if investment_amount > 0 and lumpsum_pct:
        strategy["initial_lumpsum"] = round(investment_amount * lumpsum_pct / 100, 2)

    return strategy
