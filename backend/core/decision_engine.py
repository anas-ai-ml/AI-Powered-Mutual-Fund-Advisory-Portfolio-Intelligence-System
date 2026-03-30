from typing import Any, Dict, List, Tuple

from backend.core.config import EMERGENCY_FUND_BLOCK_MONTHS, EMI_RATIO_THRESHOLD


BLOCK_CONDITIONS = [
    ("life_cover", lambda x: x > 0, "Missing life insurance"),
    ("health_cover", lambda x: x > 0, "Missing health insurance"),
    ("net_worth", lambda x: x >= 0, "Negative net worth"),
    (
        "emergency_fund_months",
        lambda x: x >= EMERGENCY_FUND_BLOCK_MONTHS,
        "Insufficient emergency fund",
    ),
]


def get_financial_priority(
    user_profile: Dict[str, Any],
    decision_trace: List[Dict[str, str]] | None = None,
) -> List[Dict[str, str]]:
    profile = dict(user_profile or {})
    trace = decision_trace if decision_trace is not None else []
    priorities: List[Dict[str, str]] = []

    if float(profile.get("life_cover", 0.0) or 0.0) == 0:
        priorities.append(
            {
                "level": "CRITICAL",
                "action": "Get Term Life Insurance",
                "reason": "No financial protection for dependents",
            }
        )
        trace.append(
            {
                "step": "priority_planning",
                "message": "Added critical action for missing life insurance",
                "level": "CRITICAL",
            }
        )

    if float(profile.get("health_cover", 0.0) or 0.0) == 0:
        priorities.append(
            {
                "level": "CRITICAL",
                "action": "Get Health Insurance",
                "reason": "Medical emergencies can destroy savings",
            }
        )
        trace.append(
            {
                "step": "priority_planning",
                "message": "Added critical action for missing health insurance",
                "level": "CRITICAL",
            }
        )

    if float(profile.get("net_worth", 0.0) or 0.0) < 0:
        priorities.append(
            {
                "level": "HIGH",
                "action": "Reduce Debt & Build Emergency Fund",
                "reason": "Negative net worth indicates financial instability",
            }
        )
        trace.append(
            {
                "step": "priority_planning",
                "message": "Added high-priority action for negative net worth",
                "level": "HIGH",
            }
        )

    if float(profile.get("emergency_fund_months", 0.0) or 0.0) < EMERGENCY_FUND_BLOCK_MONTHS:
        priorities.append(
            {
                "level": "HIGH",
                "action": "Build Emergency Fund",
                "reason": "Emergency reserves are below the minimum safety threshold",
            }
        )

    if float(profile.get("emi_ratio", 0.0) or 0.0) > EMI_RATIO_THRESHOLD:
        priorities.append(
            {
                "level": "MEDIUM",
                "action": "Reduce EMI Burden",
                "reason": "High EMI commitments reduce investment resilience",
            }
        )

    return priorities


def can_invest(
    user_profile: Dict[str, Any],
    decision_trace: List[Dict[str, str]] | None = None,
) -> Tuple[bool, str]:
    profile = dict(user_profile or {})
    trace = decision_trace if decision_trace is not None else []
    for field, condition, reason in BLOCK_CONDITIONS:
        value = profile.get(field, 0)
        if not condition(value):
            trace.append(
                {
                    "step": "eligibility_check",
                    "message": reason,
                    "level": "CRITICAL",
                }
            )
            return False, reason
    trace.append(
        {
            "step": "eligibility_check",
            "message": "Profile passed all investment eligibility checks",
            "level": "INFO",
        }
    )
    return True, "Eligible"
