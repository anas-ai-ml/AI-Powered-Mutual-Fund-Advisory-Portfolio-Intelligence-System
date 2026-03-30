from typing import Any, Dict, List

from backend.core.config import (
    ALLOCATION_TOLERANCE,
    EMI_EQUITY_MULTIPLIER,
    EMI_RATIO_THRESHOLD,
    EMERGENCY_FUND_EQUITY_MULTIPLIER,
    EMERGENCY_FUND_GUARDRAIL_MONTHS,
    LIFE_COVER_EQUITY_CAP,
)
from backend.core.logger import log_event
from backend.core.utils import safe_round


def normalize_allocation(allocation: Dict[str, Any]) -> Dict[str, float]:
    weights = {str(k): float(v or 0.0) for k, v in dict(allocation or {}).items()}
    total = sum(weights.values())
    if total == 0:
        return {k: safe_round(v, 2) for k, v in weights.items()}
    normalized = {k: safe_round((v / total) * 100.0, 2) for k, v in weights.items()}
    normalized_total = sum(normalized.values())
    if abs(normalized_total - 100.0) > ALLOCATION_TOLERANCE:
        total = sum(normalized.values())
        if total > 0:
            normalized = {k: safe_round((v / total) * 100.0, 2) for k, v in normalized.items()}
    return normalized


def apply_guardrails(
    user_profile: Dict[str, Any],
    allocation: Dict[str, Any],
    decision_trace: List[Dict[str, str]] | None = None,
) -> Dict[str, float]:
    profile = dict(user_profile or {})
    adjusted = {str(k): float(v or 0.0) for k, v in dict(allocation or {}).items()}
    trace = decision_trace if decision_trace is not None else []

    if "equity" in adjusted:
        constraints = [adjusted.get("equity", 0.0)]
        if float(profile.get("life_cover", 0.0) or 0.0) == 0:
            constraints.append(LIFE_COVER_EQUITY_CAP)
            trace.append(
                {
                    "step": "guardrail_application",
                    "message": "Equity capped due to missing life insurance",
                    "level": "HIGH",
                }
            )
            log_event({"event": "guardrail", "message": "life_cover cap"})

        if float(profile.get("emergency_fund_months", 0.0) or 0.0) < EMERGENCY_FUND_GUARDRAIL_MONTHS:
            constraints.append(adjusted.get("equity", 0.0) * EMERGENCY_FUND_EQUITY_MULTIPLIER)
            trace.append(
                {
                    "step": "guardrail_application",
                    "message": "Equity reduced due to low emergency fund coverage",
                    "level": "HIGH",
                }
            )
            log_event({"event": "guardrail", "message": "emergency fund multiplier"})

        if float(profile.get("emi_ratio", 0.0) or 0.0) > EMI_RATIO_THRESHOLD:
            constraints.append(adjusted.get("equity", 0.0) * EMI_EQUITY_MULTIPLIER)
            trace.append(
                {
                    "step": "guardrail_application",
                    "message": "Equity reduced due to high EMI ratio",
                    "level": "HIGH",
                }
            )
            log_event({"event": "guardrail", "message": "emi multiplier"})

        adjusted["equity"] = min(constraints)

    normalized = normalize_allocation(adjusted)
    trace.append(
        {
            "step": "guardrail_application",
            "message": "Allocation normalized after guardrails",
            "level": "INFO",
        }
    )
    return normalized
