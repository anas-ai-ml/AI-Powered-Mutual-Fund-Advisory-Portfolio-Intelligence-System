from backend.utils.future_value import calculate_future_value
from backend.utils.sip_calculator import calculate_required_sip, calculate_sip_future_value
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
import math


class GoalType(str, Enum):
    RETIREMENT = "retirement"
    CHILD_EDUCATION = "child_education"
    CHILD_MARRIAGE = "child_marriage"
    HOUSE_PURCHASE = "house_purchase"
    VEHICLE_PURCHASE = "vehicle_purchase"
    VACATION = "vacation"
    WEALTH_CREATION = "wealth_creation"
    EMERGENCY_FUND = "emergency_fund"
    CUSTOM = "custom"


INFLATION_MAPPING = {
    GoalType.RETIREMENT: 0.065,
    GoalType.CHILD_EDUCATION: 0.09,
    GoalType.CHILD_MARRIAGE: 0.08,
    GoalType.HOUSE_PURCHASE: 0.07,
    GoalType.VEHICLE_PURCHASE: 0.05,
    GoalType.VACATION: 0.06,
    GoalType.WEALTH_CREATION: 0.065,
    GoalType.EMERGENCY_FUND: 0.06,
    GoalType.CUSTOM: 0.065,
}


class GoalRegistry:
    def __init__(self):
        self._goals: Dict[str, Dict[str, Any]] = {}

    def add_goal(self, goal_id: str, goal_data: Dict[str, Any]) -> None:
        goal_data["created_at"] = datetime.now().isoformat()
        self._goals[goal_id] = goal_data

    def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        return self._goals.get(goal_id)

    def get_all_goals(self) -> List[Dict[str, Any]]:
        return list(self._goals.values())

    def update_goal(self, goal_id: str, updates: Dict[str, Any]) -> bool:
        if goal_id in self._goals:
            self._goals[goal_id].update(updates)
            self._goals[goal_id]["updated_at"] = datetime.now().isoformat()
            return True
        return False

    def remove_goal(self, goal_id: str) -> bool:
        if goal_id in self._goals:
            del self._goals[goal_id]
            return True
        return False

    def calculate_total_required_corpus(self) -> float:
        return sum(goal.get("future_corpus", 0) for goal in self._goals.values())

    def calculate_total_required_sip(self) -> float:
        return sum(goal.get("required_sip", 0) for goal in self._goals.values())


_goal_registry = GoalRegistry()


def get_goal_registry() -> GoalRegistry:
    return _goal_registry


def _monthly_step_up_rate(annual_step_up: float) -> float:
    return (1 + max(-0.99, float(annual_step_up))) ** (1 / 12) - 1


def _step_up_growth_factor(monthly_rate: float, monthly_step_up_rate: float, months: int) -> float:
    if months <= 0:
        return 0.0
    if abs(monthly_rate - monthly_step_up_rate) < 1e-9:
        return months * ((1 + monthly_rate) ** (months - 1))
    return (
        ((1 + monthly_rate) ** months) - ((1 + monthly_step_up_rate) ** months)
    ) / (monthly_rate - monthly_step_up_rate)


def calculate_required_step_up_sip(
    target_future_value: float,
    annual_step_up: float = 0.10,
    years: int = 10,
    return_rate: float = 0.12,
) -> float:
    months = max(0, int(years) * 12)
    if months <= 0 or target_future_value <= 0:
        return 0.0

    monthly_rate = float(return_rate) / 12.0
    monthly_step_up = _monthly_step_up_rate(annual_step_up)
    growth_factor = _step_up_growth_factor(monthly_rate, monthly_step_up, months)
    if growth_factor <= 0:
        return 0.0
    return target_future_value / growth_factor


def calculate_sip_topup(
    current_sip: float,
    annual_step_up: float = 0.10,
    years: int = 10,
    return_rate: float = 0.12,
) -> Dict[str, Any]:
    monthly_rate = float(return_rate) / 12.0
    months = max(0, int(years) * 12)
    starting_sip = max(0.0, float(current_sip))
    monthly_step_up = _monthly_step_up_rate(annual_step_up)

    if months <= 0 or starting_sip <= 0:
        return {
            "base_sip": round(starting_sip, 2),
            "starting_sip": round(starting_sip, 2),
            "annual_step_up": annual_step_up,
            "years": years,
            "return_rate": return_rate,
            "monthly_step_up_rate": round(monthly_step_up, 8),
            "final_sip": round(starting_sip, 2),
            "total_contributions": 0.0,
            "future_value": 0.0,
        }

    growth_factor = _step_up_growth_factor(monthly_rate, monthly_step_up, months)
    future_value = starting_sip * growth_factor
    if abs(monthly_step_up) < 1e-9:
        total_contributions = starting_sip * months
    else:
        total_contributions = starting_sip * (
            (((1 + monthly_step_up) ** months) - 1) / monthly_step_up
        )
    final_sip = starting_sip * ((1 + monthly_step_up) ** max(months - 1, 0))

    return {
        "base_sip": round(starting_sip, 2),
        "starting_sip": round(starting_sip, 2),
        "annual_step_up": annual_step_up,
        "years": years,
        "return_rate": return_rate,
        "monthly_step_up_rate": round(monthly_step_up, 8),
        "final_sip": round(final_sip, 2),
        "total_contributions": round(total_contributions, 2),
        "future_value": round(future_value, 2),
    }


def build_goal_sip_comparison(
    target_corpus: float,
    required_sip: float,
    years: int,
    return_rate: float,
    annual_step_up: float = 0.10,
    existing_corpus_future_value: float = 0.0,
) -> Dict[str, Any]:
    months = max(0, int(years) * 12)
    flat_sip = max(0.0, float(required_sip))
    target = max(0.0, float(target_corpus))
    future_existing = max(0.0, float(existing_corpus_future_value))
    shortfall = max(0.0, target - future_existing)
    flat_total_invested = flat_sip * months

    if annual_step_up <= 0:
        topup_starting_sip = flat_sip
        topup_projection = {
            "total_contributions": round(flat_total_invested, 2),
        }
    else:
        topup_starting_sip = calculate_required_step_up_sip(
            target_future_value=shortfall,
            annual_step_up=annual_step_up,
            years=years,
            return_rate=return_rate,
        )
        topup_projection = calculate_sip_topup(
            current_sip=topup_starting_sip,
            annual_step_up=annual_step_up,
            years=years,
            return_rate=return_rate,
        )

    topup_total_invested = float(topup_projection.get("total_contributions", 0.0))
    step_up_label = f"{annual_step_up * 100:.0f}% Annual Top-Up"
    note = (
        f"A {annual_step_up * 100:.0f}% annual step-up allows you to start with a lower SIP "
        f"(₹{topup_starting_sip:,.0f} vs ₹{flat_sip:,.0f}) and still reach the same corpus."
        if annual_step_up > 0 and topup_starting_sip < flat_sip
        else "Flat SIP and step-up SIP are identical at a 0% annual top-up assumption."
    )

    return {
        "annual_step_up_pct": round(float(annual_step_up) * 100.0, 2),
        "flat": {
            "mode": "Flat SIP",
            "monthly_sip_year_1": round(flat_sip, 2),
            "corpus_at_goal": round(target, 2),
            "total_invested": round(flat_total_invested, 2),
            "wealth_multiplier": round(target / flat_total_invested, 2)
            if flat_total_invested > 0
            else 0.0,
        },
        "step_up": {
            "mode": step_up_label,
            "monthly_sip_year_1": round(topup_starting_sip, 2),
            "corpus_at_goal": round(target, 2),
            "total_invested": round(topup_total_invested, 2),
            "wealth_multiplier": round(target / topup_total_invested, 2)
            if topup_total_invested > 0
            else 0.0,
        },
        "note": note,
    }


def validate_goal_inputs(
    goal_type: str,
    years_to_goal: int,
    present_cost: float,
    current_age: Optional[int] = None,
    retirement_age: int = 60,
) -> Dict[str, Any]:
    violations = []
    warnings = []

    if years_to_goal <= 0:
        violations.append("Years to goal must be greater than 0")
    elif years_to_goal > 40:
        warnings.append(
            "Very long horizon (>40 years) - assumptions may change significantly"
        )

    if present_cost <= 0:
        violations.append("Present cost must be greater than 0")
    elif present_cost > 100000000:
        warnings.append(
            "Very large corpus target - consider breaking into smaller goals"
        )

    if goal_type == GoalType.RETIREMENT.value:
        if current_age and years_to_goal != (retirement_age - current_age):
            warnings.append(
                f"Years to goal should be {retirement_age - current_age} for retirement at age {retirement_age}"
            )
        if current_age and current_age >= retirement_age:
            violations.append(
                f"Current age {current_age} must be less than retirement age {retirement_age}"
            )

    if goal_type == GoalType.CHILD_EDUCATION.value:
        if years_to_goal > 25:
            warnings.append("Education goal horizon >25 years seems unusually long")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
    }


def calculate_retirement_goal(
    current_age: int,
    current_monthly_expense: float,
    expected_return_rate: float,
    retirement_age: int = 60,
    existing_corpus: float = 0.0,
    annual_sip_step_up: float = 0.0,
) -> Dict[str, Any]:
    """
    Calculate Retirement Corpus and Required SIP.
    Assumes Indian Inflation (2026 Outlook) = 6.5%.
    Factors in existing investment corpus and target retirement age.
    """
    years_to_goal = retirement_age - current_age

    if years_to_goal <= 0:
        return {
            "goal_name": "Retirement",
            "years_to_goal": 0,
            "future_corpus": 0.0,
            "required_sip": 0.0,
        }

    inflation_rate = INFLATION_MAPPING[GoalType.RETIREMENT]
    future_monthly_expense = calculate_future_value(
        current_monthly_expense, inflation_rate, years_to_goal
    )

    total_future_corpus = future_monthly_expense * 12 * 25

    fv_existing_corpus = existing_corpus * ((1 + expected_return_rate) ** years_to_goal)

    shortfall = max(0.0, total_future_corpus - fv_existing_corpus)

    required_sip = calculate_required_sip(
        shortfall, expected_return_rate, years_to_goal
    )
    sip_comparison = build_goal_sip_comparison(
        target_corpus=total_future_corpus,
        required_sip=required_sip,
        years=years_to_goal,
        return_rate=expected_return_rate,
        annual_step_up=annual_sip_step_up,
        existing_corpus_future_value=fv_existing_corpus,
    )

    return {
        "goal_name": "Retirement",
        "goal_type": GoalType.RETIREMENT.value,
        "years_to_goal": years_to_goal,
        "total_future_corpus": round(total_future_corpus, 2),
        "fv_existing_corpus": round(fv_existing_corpus, 2),
        "shortfall_corpus": round(shortfall, 2),
        "future_corpus": round(total_future_corpus, 2),
        "required_sip": round(required_sip, 2),
        "inflation_rate": inflation_rate,
        "monthly_expense_at_retirement": round(future_monthly_expense, 2),
        "annual_sip_step_up": round(float(annual_sip_step_up), 4),
        "sip_comparison": sip_comparison,
    }


def calculate_child_education_goal(
    present_cost: float,
    years_to_goal: int,
    expected_return_rate: float,
    current_age: Optional[int] = None,
    child_age: Optional[int] = None,
    annual_sip_step_up: float = 0.0,
) -> Dict[str, Any]:
    """
    Calculate Child Education Corpus and Required SIP.
    Assumes Indian Education Inflation (2026 Outlook) = 9%.
    """
    if years_to_goal <= 0:
        return {
            "goal_name": "Child Education",
            "years_to_goal": 0,
            "future_corpus": float(present_cost),
            "required_sip": 0.0,
        }

    inflation_rate = INFLATION_MAPPING[GoalType.CHILD_EDUCATION]
    future_corpus = calculate_future_value(present_cost, inflation_rate, years_to_goal)

    required_sip = calculate_required_sip(
        future_corpus, expected_return_rate, years_to_goal
    )
    sip_comparison = build_goal_sip_comparison(
        target_corpus=future_corpus,
        required_sip=required_sip,
        years=years_to_goal,
        return_rate=expected_return_rate,
        annual_step_up=annual_sip_step_up,
    )

    result = {
        "goal_name": "Child Education",
        "goal_type": GoalType.CHILD_EDUCATION.value,
        "years_to_goal": years_to_goal,
        "future_corpus": round(future_corpus, 2),
        "required_sip": round(required_sip, 2),
        "inflation_rate": inflation_rate,
        "present_cost": present_cost,
        "annual_sip_step_up": round(float(annual_sip_step_up), 4),
        "sip_comparison": sip_comparison,
    }

    if current_age and child_age:
        result["years_until_education"] = (
            child_age - current_age if child_age > current_age else years_to_goal
        )

    return result


def calculate_custom_goal(
    goal_name: str,
    present_cost: float,
    years_to_goal: int,
    expected_return_rate: float,
    goal_type: str = GoalType.CUSTOM.value,
    custom_inflation: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate custom goal with optional custom inflation rate.
    """
    if years_to_goal <= 0:
        return {
            "goal_name": goal_name,
            "years_to_goal": 0,
            "future_corpus": float(present_cost),
            "required_sip": 0.0,
        }

    inflation_rate = (
        custom_inflation
        if custom_inflation
        else INFLATION_MAPPING.get(
            GoalType(goal_type), INFLATION_MAPPING[GoalType.CUSTOM]
        )
    )

    future_corpus = calculate_future_value(present_cost, inflation_rate, years_to_goal)

    required_sip = calculate_required_sip(
        future_corpus, expected_return_rate, years_to_goal
    )

    return {
        "goal_name": goal_name,
        "goal_type": goal_type,
        "years_to_goal": years_to_goal,
        "present_cost": present_cost,
        "future_corpus": round(future_corpus, 2),
        "required_sip": round(required_sip, 2),
        "inflation_rate": inflation_rate,
        "expected_return_rate": expected_return_rate,
    }


def calculate_goal_with_sip_topup(
    goal_data: Dict[str, Any], annual_step_up: float = 0.10
) -> Dict[str, Any]:
    """
    Calculate goal with SIP top-up (step-up) strategy.
    """
    required_sip = goal_data.get("required_sip", 0)
    years = goal_data.get("years_to_goal", 10)
    return_rate = goal_data.get("expected_return_rate", 0.12)
    target_corpus = goal_data.get("future_corpus", 0.0)
    existing_corpus_future_value = goal_data.get("fv_existing_corpus", 0.0)
    sip_comparison = build_goal_sip_comparison(
        target_corpus=target_corpus,
        required_sip=required_sip,
        years=years,
        return_rate=return_rate,
        annual_step_up=annual_step_up,
        existing_corpus_future_value=existing_corpus_future_value,
    )
    topup_result = calculate_sip_topup(
        sip_comparison["step_up"]["monthly_sip_year_1"],
        annual_step_up,
        years,
        return_rate,
    )

    return {
        **goal_data,
        "annual_sip_step_up": round(float(annual_step_up), 4),
        "sip_comparison": sip_comparison,
        "with_step_up": {
            "base_sip": sip_comparison["step_up"]["monthly_sip_year_1"],
            "final_sip": topup_result["final_sip"],
            "total_contributions": topup_result["total_contributions"],
            "future_value": topup_result["future_value"],
            "additional_corpus": round(
                topup_result["future_value"] - (required_sip * years * 12), 2
            ),
        },
    }
