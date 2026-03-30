from typing import Dict, List

from backend.core.utils import clamp, safe_round


def compute_market_stability(
    inflation: float,
    vix: float,
    geo_risk: float,
    decision_trace: List[Dict[str, str]] | None = None,
) -> float:
    trace = decision_trace if decision_trace is not None else []
    inflation_score = clamp((float(inflation) - 3.0) / 12.0, 0.0, 1.0)
    vix_score = clamp((float(vix) - 12.0) / 23.0, 0.0, 1.0)
    geo_score = clamp(float(geo_risk), 0.0, 1.0)

    composite_risk = (
        0.35 * inflation_score +
        0.35 * geo_score +
        0.30 * vix_score
    )
    stability = clamp(1.0 - composite_risk, 0.0, 1.0)
    trace.append(
        {
            "step": "macro_assessment",
            "message": f"Market stability computed at {safe_round(stability, 4):.4f}",
            "level": "INFO",
        }
    )
    return safe_round(stability, 4)
