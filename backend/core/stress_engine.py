from typing import Any, Dict, List

from backend.core.utils import clamp, safe_round


def _scenario(severity: str, impact_summary: str, impact_value: float, **extra: Any) -> Dict[str, Any]:
    return {
        "severity": severity,
        "impact_summary": impact_summary,
        "impact_value": safe_round(impact_value, 2),
        **extra,
    }


def run_stress_tests(
    user_profile: Dict[str, Any],
    goals: List[Dict[str, Any]] | None,
    allocation: Dict[str, Any],
    decision_trace: List[Dict[str, str]] | None = None,
) -> Dict[str, Dict[str, Any]]:
    profile = dict(user_profile or {})
    alloc = dict(allocation or {})
    trace = decision_trace if decision_trace is not None else []

    if not goals:
        trace.append(
            {
                "step": "stress_test",
                "message": "Stress test skipped: goals unavailable",
                "level": "INFO",
            }
        )
        return {}

    existing_corpus = float(profile.get("existing_corpus", 0.0) or 0.0)
    equity_pct = clamp(float(alloc.get("equity", 0.0) or 0.0) / 100.0, 0.0, 1.0)
    monthly_income = float(profile.get("monthly_income", 0.0) or 0.0)
    effective_savings = float(profile.get("effective_monthly_savings", 0.0) or 0.0)
    total_goal_value = sum(
        float(goal.get("future_corpus", goal.get("target_amount", 0.0)) or 0.0)
        for goal in goals
        if isinstance(goal, dict)
    )

    market_crash_impact = existing_corpus * equity_pct * 0.30
    market_crash_severity = "HIGH" if market_crash_impact >= existing_corpus * 0.15 else "MEDIUM" if market_crash_impact > 0 else "LOW"

    income_loss_impact = max(monthly_income * 6.0, abs(min(effective_savings, 0.0)) * 6.0)
    income_loss_severity = "HIGH" if income_loss_impact >= monthly_income * 6.0 else "MEDIUM" if income_loss_impact > 0 else "LOW"

    inflation_spike_impact = total_goal_value * 0.10
    inflation_spike_severity = "HIGH" if inflation_spike_impact >= total_goal_value * 0.08 else "MEDIUM" if inflation_spike_impact > 0 else "LOW"

    results = {
        "market_crash": _scenario(
            market_crash_severity,
            "30% market crash reduces equity-linked corpus value.",
            market_crash_impact,
        ),
        "income_loss": _scenario(
            income_loss_severity,
            "Six months of income loss disrupts contribution capacity.",
            income_loss_impact,
        ),
        "inflation_spike": _scenario(
            inflation_spike_severity,
            "Inflation spike raises future goal costs.",
            inflation_spike_impact,
        ),
    }
    trace.append(
        {
            "step": "stress_test",
            "message": "Stress scenarios computed for crash, income loss, and inflation spike",
            "level": "INFO",
        }
    )
    return results
