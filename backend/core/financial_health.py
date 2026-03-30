from typing import Any, Dict, List

from backend.core.config import EMI_RATIO_THRESHOLD, EMERGENCY_FUND_BLOCK_MONTHS, HEALTH_BANDS
from backend.core.utils import safe_round


def _band_for_score(score: float) -> str:
    for band, bounds in HEALTH_BANDS.items():
        low, high = bounds
        if band == "strong" and low <= score <= high:
            return band
        if low <= score < high:
            return band
    return "fragile"


def compute_financial_health(
    user_profile: Dict[str, Any],
    decision_trace: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    profile = dict(user_profile or {})
    trace = decision_trace if decision_trace is not None else []
    score = 100.0
    drivers: List[str] = []

    if float(profile.get("life_cover", 0.0) or 0.0) == 0:
        score -= 30
        drivers.append("No life cover: -30")
    if float(profile.get("health_cover", 0.0) or 0.0) == 0:
        score -= 20
        drivers.append("No health cover: -20")
    if float(profile.get("net_worth", 0.0) or 0.0) < 0:
        score -= 20
        drivers.append("Negative net worth: -20")
    if float(profile.get("emergency_fund_months", 0.0) or 0.0) < EMERGENCY_FUND_BLOCK_MONTHS:
        score -= 15
        drivers.append("Emergency fund below 3 months: -15")
    if float(profile.get("emi_ratio", 0.0) or 0.0) > EMI_RATIO_THRESHOLD:
        score -= 15
        drivers.append("EMI ratio above threshold: -15")

    final_score = max(safe_round(score, 1), 0.0)
    band = _band_for_score(final_score)
    trace.append(
        {
            "step": "financial_health",
            "message": f"Financial health scored at {final_score:.1f} ({band})",
            "level": "INFO",
        }
    )
    return {"score": final_score, "band": band, "drivers": drivers}
