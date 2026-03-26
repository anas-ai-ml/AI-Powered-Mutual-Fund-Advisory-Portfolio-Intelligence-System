from typing import Any, Dict, Optional

from backend.engines.v1.risk_engine import (
    compute_factor_contributions,
    compute_risk as _compute_risk_v1,
    risk_score_to_allocation,
)


def _normalize_behavior(behavior: Any) -> int:
    if isinstance(behavior, (int, float)):
        return max(1, min(3, int(behavior)))

    normalized = str(behavior or "").strip().lower()
    mapping = {
        "conservative": 1,
        "prefers stability": 1,
        "stability": 1,
        "low risk": 1,
        "moderate": 2,
        "balanced": 2,
        "aggressive": 3,
        "high risk": 3,
    }
    return mapping.get(normalized, 2)


def _default_macro_data() -> Dict[str, float]:
    return {
        "macro_context_score": 0.75,
        "vix": 15.0,
        "inflation": 5.0,
        "repo_rate": 6.5,
    }


def compute_risk(
    user_input: Dict[str, Any], macro_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    normalized_input = dict(user_input)
    normalized_input["behavior"] = _normalize_behavior(user_input.get("behavior", 2))
    result = _compute_risk_v1(normalized_input, macro_data or _default_macro_data())
    score = float(result.get("score", 5.0))
    if score > 7.0:
        result["category"] = "Aggressive"
    elif score < 5.0:
        result["category"] = "Conservative"
    else:
        result["category"] = "Moderate"

    factor_contributions = {
        factor["name"]: float(factor.get("contribution", 0.0))
        for factor in result.get("factors", [])
    }
    result["factor_contributions"] = factor_contributions
    result["recommended_allocation"] = risk_score_to_allocation(result["score"])
    return result


def calculate_risk_score(
    age: int,
    dependents: int,
    monthly_income: float,
    monthly_savings: float,
    behavioral_trait: Optional[str] = None,
    behavior: Optional[str] = None,
) -> Dict[str, Any]:
    selected_behavior = behavior if behavior is not None else behavioral_trait
    user_input = {
        "age": float(age),
        "dependents": float(dependents),
        "income": float(monthly_income),
        "savings": float(monthly_savings),
        "behavior": _normalize_behavior(selected_behavior),
    }
    return compute_risk(user_input, _default_macro_data())
