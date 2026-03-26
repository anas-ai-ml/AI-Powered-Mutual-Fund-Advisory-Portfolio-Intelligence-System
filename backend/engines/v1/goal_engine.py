from backend.utils.future_value import calculate_future_value
from backend.utils.sip_calculator import calculate_required_sip
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


def calculate_sip_topup(
    current_sip: float,
    annual_step_up: float = 0.10,
    years: int = 10,
    return_rate: float = 0.12,
) -> Dict[str, Any]:
    monthly_rate = return_rate / 12
    months = years * 12

    total_contributions = 0
    current_sip_amount = current_sip

    for year in range(years):
        yearly_contribution = current_sip_amount * 12
        total_contributions += yearly_contribution

        for month in range(12):
            if month == 0 and year > 0:
                current_sip_amount *= 1 + annual_step_up

    if monthly_rate > 0:
        future_value = 0
        current_sip_amount = current_sip
        for year in range(years):
            for month in range(12):
                if month == 0 and year > 0:
                    current_sip_amount *= 1 + annual_step_up
                future_value += current_sip_amount * (
                    (1 + monthly_rate) ** (months - year * 12 - month)
                )
    else:
        future_value = total_contributions

    return {
        "base_sip": current_sip,
        "annual_step_up": annual_step_up,
        "years": years,
        "return_rate": return_rate,
        "final_sip": round(current_sip * ((1 + annual_step_up) ** years), 2),
        "total_contributions": round(total_contributions, 2),
        "future_value": round(future_value, 2),
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
    }


def calculate_child_education_goal(
    present_cost: float,
    years_to_goal: int,
    expected_return_rate: float,
    current_age: Optional[int] = None,
    child_age: Optional[int] = None,
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

    result = {
        "goal_name": "Child Education",
        "goal_type": GoalType.CHILD_EDUCATION.value,
        "years_to_goal": years_to_goal,
        "future_corpus": round(future_corpus, 2),
        "required_sip": round(required_sip, 2),
        "inflation_rate": inflation_rate,
        "present_cost": present_cost,
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

    topup_result = calculate_sip_topup(required_sip, annual_step_up, years, return_rate)

    return {
        **goal_data,
        "with_step_up": {
            "base_sip": required_sip,
            "final_sip": topup_result["final_sip"],
            "total_contributions": topup_result["total_contributions"],
            "future_value": topup_result["future_value"],
            "additional_corpus": round(
                topup_result["future_value"] - (required_sip * years * 12), 2
            ),
        },
    }
