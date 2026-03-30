from typing import Dict, List

from backend.core.config import CONFIDENCE_BANDS
from backend.core.utils import clamp, safe_round


def _confidence_band(value: float) -> str:
    for band, bounds in CONFIDENCE_BANDS.items():
        low, high = bounds
        if band == "high" and low <= value <= high:
            return band
        if low <= value < high:
            return band
    return "low"


def compute_confidence(
    monte_carlo_prob: float,
    market_stability: float,
    income_stability: float,
    decision_trace: List[Dict[str, str]] | None = None,
) -> Dict[str, float | str]:
    trace = decision_trace if decision_trace is not None else []
    raw_probability = float(monte_carlo_prob or 0.0)
    normalized_probability = raw_probability / 100.0 if raw_probability > 1.0 else raw_probability
    normalized_probability = clamp(normalized_probability, 0.0, 1.0)
    stability = clamp(market_stability, 0.0, 1.0)
    income = clamp(income_stability, 0.0, 1.0)
    composite = clamp(normalized_probability * stability * income, 0.0, 1.0)
    band = _confidence_band(composite)
    result = {
        "raw_probability": safe_round(raw_probability, 1),
        "normalized_probability": safe_round(normalized_probability, 4),
        "market_stability": safe_round(stability, 4),
        "income_stability": safe_round(income, 4),
        "composite_confidence": safe_round(composite, 4),
        "display_confidence_pct": safe_round(composite * 100.0, 1),
        "band": band,
    }
    trace.append(
        {
            "step": "confidence_computation",
            "message": f"Composite confidence computed at {result['composite_confidence']:.4f} ({band})",
            "level": "INFO",
        }
    )
    return result
