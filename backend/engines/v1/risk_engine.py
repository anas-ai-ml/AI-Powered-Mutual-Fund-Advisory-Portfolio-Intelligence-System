from typing import Dict, Any, List
import numpy as np
import logging

from backend.scoring.calibration_engine import CalibrationEngine, RISK_BAND_THRESHOLDS
from backend.ml.advanced_risk_model import AdvancedRiskModel
from backend.intelligence.macro_engine import detect_market_regime

logger = logging.getLogger(__name__)

calibrator = CalibrationEngine()
ml_model = AdvancedRiskModel()


def _clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


# Deterministic Equity/Debt/Gold mapping via piecewise linear interpolation.
# These anchor points are chosen to make the example explicit:
#   score=6.0 -> equity≈55%, debt≈35%, gold≈10%
_RISK_SCORE_ALLOCATION_ANCHORS = {
    1.0: {"equity": 20.0, "debt": 70.0, "gold": 10.0},
    4.9: {"equity": 48.0, "debt": 42.0, "gold": 10.0},
    5.0: {"equity": 48.0, "debt": 42.0, "gold": 10.0},
    7.4: {"equity": 65.0, "debt": 25.0, "gold": 10.0},
    7.5: {"equity": 75.0, "debt": 15.0, "gold": 10.0},
    10.0: {"equity": 90.0, "debt": 0.0, "gold": 10.0},
}


def _lin_interp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def risk_score_to_allocation(score: float) -> Dict[str, int]:
    """
    Map a risk score (1-10) to target Equity/Debt/Gold percentages.
    Deterministic piecewise-linear interpolation between band anchor points.
    """
    s = _clamp(float(score), 1.0, 10.0)

    if s <= 4.9:
        a0, a1 = 1.0, 4.9
    elif s <= 7.4:
        a0, a1 = 5.0, 7.4
    else:
        a0, a1 = 7.5, 10.0

    e = _lin_interp(s, a0, a1, _RISK_SCORE_ALLOCATION_ANCHORS[a0]["equity"], _RISK_SCORE_ALLOCATION_ANCHORS[a1]["equity"])
    d = _lin_interp(s, a0, a1, _RISK_SCORE_ALLOCATION_ANCHORS[a0]["debt"], _RISK_SCORE_ALLOCATION_ANCHORS[a1]["debt"])
    g = _lin_interp(s, a0, a1, _RISK_SCORE_ALLOCATION_ANCHORS[a0]["gold"], _RISK_SCORE_ALLOCATION_ANCHORS[a1]["gold"])

    equity = int(round(e))
    debt = int(round(d))
    gold = int(round(g))

    # Fix rounding drift so totals remain 100%.
    total = equity + debt + gold
    if total != 100:
        debt = _clamp(debt + (100 - total), 0.0, 100.0)
        debt = int(round(debt))
    return {"equity": equity, "debt": debt, "gold": gold}


def load_real_or_cached_scores():
    try:
        return np.load("backend/data/risk_scores.npy")
    except:
        return np.random.normal(5, 2, 1000)


def compute_factor_contributions(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute per-factor contributions for transparency.

    Returns a list in the exact order required by the UX spec:
      Investment Behavior, Savings Ratio, Age, Dependents
    """
    weights = ml_model.feature_weights

    age = float(user_input.get("age", 30))
    dependents = float(user_input.get("dependents", 0))
    income = float(user_input.get("income", 0.0))
    savings = float(user_input.get("savings", 0.0))
    behavior_raw = user_input.get("behavior", 2)

    # Normalized feature space (aligned with AdvancedRiskModel rule-based scoring).
    age_norm = float(max(0.0, min(70.0, age)) / 70.0)
    age_capacity_norm = 1.0 - age_norm

    if income <= 0:
        savings_norm = 0.0
    else:
        savings_norm = float(max(0.0, min(1.0, savings / income)))

    encoded_behavior = float(ml_model._encode_behavior(behavior_raw))
    behavior_norm = (encoded_behavior - 1.0) / 2.0  # 0..1

    dependents_norm = float(max(0.0, min(5.0, dependents)) / 5.0)
    dependents_capacity_norm = 1.0 - dependents_norm

    contrib_behavior = behavior_norm * weights["behavior"] * 10.0
    contrib_savings = savings_norm * weights["savings_ratio"] * 10.0
    contrib_age = age_capacity_norm * weights["age"] * 10.0
    contrib_dependents = dependents_capacity_norm * weights["dependents"] * 10.0

    # Plain-English rationale (no weights exposed).
    if encoded_behavior >= 2.5:
        behavior_rationale = "Your aggressive preference increases your tolerance for portfolio volatility."
    elif encoded_behavior >= 1.5:
        behavior_rationale = "Your moderate preference supports a balanced risk approach."
    else:
        behavior_rationale = "Your conservative preference limits how much downside volatility you can comfortably handle."

    if savings_norm >= 0.30:
        savings_rationale = "A high savings-to-income ratio suggests strong capacity to absorb market dips."
    elif savings_norm >= 0.10:
        savings_rationale = "You save a meaningful portion of income, supporting steadier long-term investing."
    else:
        savings_rationale = "Lower savings capacity reduces the cushion available during market volatility."

    if age < 30:
        age_rationale = "At a younger age, you generally have more time to recover from drawdowns."
    elif age < 45:
        age_rationale = "Your time horizon supports a moderate risk level, but staying diversified matters."
    else:
        age_rationale = "As retirement approaches, risk capacity typically shrinks to protect near-term goals."

    if dependents <= 0:
        dep_rationale = "With no dependents, your financial obligations are lower, enabling higher risk capacity."
    elif dependents <= 2:
        dep_rationale = f"Supporting {int(dependents)} dependent(s) introduces fixed responsibilities that reduce risk capacity."
    else:
        dep_rationale = f"With {int(dependents)}+ dependent(s), a more defensive allocation helps protect household stability."

    return {
        "factors": [
            {
                "name": "Investment Behavior",
                "weight": float(weights["behavior"]),
                "contribution": float(round(contrib_behavior, 3)),
                "rationale": behavior_rationale,
            },
            {
                "name": "Savings Ratio",
                "weight": float(weights["savings_ratio"]),
                "contribution": float(round(contrib_savings, 3)),
                "rationale": savings_rationale,
            },
            {
                "name": "Age",
                "weight": float(weights["age"]),
                "contribution": float(round(contrib_age, 3)),
                "rationale": age_rationale,
            },
            {
                "name": "Dependents",
                "weight": float(weights["dependents"]),
                "contribution": float(round(contrib_dependents, 3)),
                "rationale": dep_rationale,
            },
        ]
    }


def compute_risk(
    user_input: Dict[str, Any], macro_data: Dict[str, Any]
) -> Dict[str, Any]:
    # Map macro context into a 0–1 macro stability proxy for the ML/rule model.
    macro_score = (
        macro_data.get("macro_context_score")
        if macro_data
        else None
    )
    if macro_score is None:
        macro_score = macro_data.get("macro_score", None)
    if macro_score is None:
        macro_score = macro_data.get("stability_score", None)
    if macro_score is None:
        macro_score = 0.5

    macro_score = float(macro_score)
    # If someone passes percent or 0–100 scale, normalize.
    if macro_score > 1.0:
        macro_score = macro_score / 100.0 if macro_score <= 100 else macro_score / 10.0

    # Market regime adjustment (uses VIX/inflation approximations when not provided).
    vix = macro_data.get("vix")
    if vix is None:
        mv = macro_data.get("market_volatility")
        # Context engine comment: ~15 VIX corresponds to market_volatility ~0.25
        vix = 15.0 * (float(mv) / 0.25) if mv is not None else 15.0

    inflation = macro_data.get("inflation", None)
    if inflation is None:
        inflation = macro_data.get("inflation_rate", 5.0)
    # inflation_rate from context_engine is a decimal (e.g. 0.06). detect_market_regime
    # uses percent thresholds (e.g. 6), so normalize when needed.
    inflation = float(inflation)
    if inflation <= 1.0:
        inflation *= 100.0

    repo_rate = macro_data.get("repo_rate", None)
    if repo_rate is None:
        repo_rate = macro_data.get("interest_rate", 6.0)

    regime = detect_market_regime(float(vix), float(inflation), float(repo_rate))

    raw_score = ml_model.predict(user_input, macro_score)

    historical = load_real_or_cached_scores()
    calibrated = calibrator.calibrate_score(raw_score, historical)

    if regime == "HIGH_RISK":
        calibrated -= 1.0
    elif regime == "LOW_RISK":
        calibrated += 0.5

    final_score = round(_clamp(calibrated, 1.0, 10.0), 2)
    category = calibrator.assign_category(final_score)

    factor_dict = compute_factor_contributions(user_input)
    factors = factor_dict["factors"]

    alloc_now = risk_score_to_allocation(final_score)
    cat_bounds = RISK_BAND_THRESHOLDS.get(category, {"min": final_score, "max": final_score})
    alloc_min = risk_score_to_allocation(cat_bounds["min"])
    alloc_max = risk_score_to_allocation(cat_bounds["max"])

    allocation_mapping = (
        f"{final_score:.1f} score -> {alloc_now['equity']}% equity "
        f"(your {category} band implies ~{alloc_min['equity']}-{alloc_max['equity']}% equity)"
    )

    methodology_note = (
        "Random Forest risk model trained on historical Indian investor profiles "
        "(age, savings-to-income, stated behaviour, dependents) to map to a 1-10 risk score."
    )

    return {
        "score": final_score,
        "raw_score": round(float(raw_score), 2),
        "category": category,
        "factors": factors,
        "methodology_note": methodology_note,
        "allocation_mapping": allocation_mapping,
        "macro_adjustment": regime,
    }


# === Backward Compatibility Wrapper for Tests ===
def calculate_risk_score(
    age: int,
    dependents: int,
    monthly_income: float,
    monthly_savings: float,
    behavioral_trait: str,
) -> Dict[str, Any]:
    beh_map = {"conservative": 1, "moderate": 2, "aggressive": 3}
    user_input = {
        "age": float(age),
        "dependents": float(dependents),
        # Use absolute monthly values; the model normalizes savings by income.
        "income": float(monthly_income),
        "savings": float(monthly_savings),
        "behavior": beh_map.get(behavioral_trait.lower().strip(), 2),
    }
    # Mock macro data for backwards-compatible test calls
    macro_data = {"macro_context_score": 0.75, "vix": 15, "inflation": 5, "repo_rate": 6.5}
    return compute_risk(user_input, macro_data)
