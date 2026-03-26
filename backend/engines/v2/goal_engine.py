from typing import Any, Dict, Optional

from backend.engines.v1.goal_engine import (
    GoalRegistry,
    GoalType,
    INFLATION_MAPPING,
    build_goal_sip_comparison,
    calculate_retirement_goal as _calculate_retirement_goal_v1,
    calculate_child_education_goal,
    calculate_custom_goal,
    calculate_goal_with_sip_topup,
    calculate_required_step_up_sip,
    calculate_sip_topup,
    get_goal_registry,
    validate_goal_inputs,
)
from backend.utils.future_value import calculate_future_value
from backend.utils.sip_calculator import calculate_required_sip

_POST_RETIREMENT_RETURN_RATE = 0.07


def calculate_post_retirement_income_corpus(
    post_retirement_income: float,
    post_retirement_years: int = 25,
    withdrawal_phase_return_rate: float = _POST_RETIREMENT_RETURN_RATE,
) -> Dict[str, Any]:
    monthly_income = max(0.0, float(post_retirement_income))
    years = max(0, int(post_retirement_years))
    months = years * 12
    monthly_rate = float(withdrawal_phase_return_rate) / 12.0

    if monthly_income <= 0 or months <= 0:
        return {
            "monthly_income": monthly_income,
            "years": years,
            "months": months,
            "withdrawal_phase_return_rate": float(withdrawal_phase_return_rate),
            "annuity_corpus_required": 0.0,
        }

    if monthly_rate == 0:
        annuity_corpus = monthly_income * months
    else:
        annuity_corpus = monthly_income * (1 - (1 + monthly_rate) ** (-months)) / monthly_rate

    return {
        "monthly_income": monthly_income,
        "years": years,
        "months": months,
        "withdrawal_phase_return_rate": float(withdrawal_phase_return_rate),
        "annuity_corpus_required": round(annuity_corpus, 2),
    }


def calculate_retirement_goal(
    current_age: int,
    current_monthly_expense: float,
    expected_return_rate: float,
    retirement_age: int = 60,
    existing_corpus: float = 0.0,
    post_retirement_income: Optional[float] = None,
    post_retirement_years: int = 25,
    include_post_retirement_income: bool = False,
    annual_sip_step_up: float = 0.0,
) -> Dict[str, Any]:
    result = _calculate_retirement_goal_v1(
        current_age=current_age,
        current_monthly_expense=current_monthly_expense,
        expected_return_rate=expected_return_rate,
        retirement_age=retirement_age,
        existing_corpus=existing_corpus,
        annual_sip_step_up=annual_sip_step_up,
    )

    if not include_post_retirement_income:
        return result

    distribution = calculate_post_retirement_income_corpus(
        post_retirement_income=post_retirement_income or 0.0,
        post_retirement_years=post_retirement_years,
    )
    annuity_corpus_required = float(distribution["annuity_corpus_required"])
    accumulation_corpus = float(result.get("future_corpus", 0.0))
    years_to_goal = int(result.get("years_to_goal", 0))
    fv_existing_corpus = float(result.get("fv_existing_corpus", 0.0))

    target_corpus = max(accumulation_corpus, annuity_corpus_required)
    target_shortfall = max(0.0, target_corpus - fv_existing_corpus)
    target_required_sip = calculate_required_sip(
        target_shortfall, expected_return_rate, years_to_goal
    ) if years_to_goal > 0 else 0.0
    sip_increase = max(0.0, float(target_required_sip) - float(result.get("required_sip", 0.0)))

    corpus_gap = round(accumulation_corpus - annuity_corpus_required, 2)
    distribution.update(
        {
            "shortfall_or_surplus": corpus_gap,
            "status": "surplus" if corpus_gap >= 0 else "shortfall",
            "additional_sip_required": round(sip_increase, 2),
        }
    )
    result["distribution_phase"] = distribution
    result["target_corpus_with_income"] = round(target_corpus, 2)
    result["required_sip_with_income"] = round(target_required_sip, 2)
    result["post_retirement_income_planning_enabled"] = True
    result["sip_comparison"] = build_goal_sip_comparison(
        target_corpus=target_corpus,
        required_sip=target_required_sip,
        years=years_to_goal,
        return_rate=expected_return_rate,
        annual_step_up=annual_sip_step_up,
        existing_corpus_future_value=fv_existing_corpus,
    )
    return result


def _calculate_standard_goal(
    goal_name: str,
    goal_type: GoalType,
    present_cost: float,
    years_to_goal: int,
    expected_return_rate: float,
) -> Dict[str, Any]:
    if years_to_goal <= 0:
        return {
            "goal_name": goal_name,
            "goal_type": goal_type.value,
            "years_to_goal": 0,
            "future_corpus": float(present_cost),
            "required_sip": 0.0,
            "inflation_rate": INFLATION_MAPPING[goal_type],
        }

    inflation_rate = INFLATION_MAPPING[goal_type]
    future_corpus = calculate_future_value(present_cost, inflation_rate, years_to_goal)
    required_sip = calculate_required_sip(
        future_corpus, expected_return_rate, years_to_goal
    )
    return {
        "goal_name": goal_name,
        "goal_type": goal_type.value,
        "present_cost": present_cost,
        "years_to_goal": years_to_goal,
        "future_corpus": round(future_corpus, 2),
        "required_sip": round(required_sip, 2),
        "inflation_rate": inflation_rate,
        "expected_return_rate": expected_return_rate,
    }


def calculate_child_marriage_goal(
    present_cost: float, years_to_goal: int, expected_return_rate: float
) -> Dict[str, Any]:
    return _calculate_standard_goal(
        "Child Marriage",
        GoalType.CHILD_MARRIAGE,
        present_cost,
        years_to_goal,
        expected_return_rate,
    )


def calculate_house_purchase_goal(
    present_cost: float, years_to_goal: int, expected_return_rate: float
) -> Dict[str, Any]:
    return _calculate_standard_goal(
        "House Purchase",
        GoalType.HOUSE_PURCHASE,
        present_cost,
        years_to_goal,
        expected_return_rate,
    )


def calculate_vehicle_purchase_goal(
    present_cost: float, years_to_goal: int, expected_return_rate: float
) -> Dict[str, Any]:
    return _calculate_standard_goal(
        "Vehicle Purchase",
        GoalType.VEHICLE_PURCHASE,
        present_cost,
        years_to_goal,
        expected_return_rate,
    )


def calculate_vacation_goal(
    present_cost: float, years_to_goal: int, expected_return_rate: float
) -> Dict[str, Any]:
    return _calculate_standard_goal(
        "Vacation",
        GoalType.VACATION,
        present_cost,
        years_to_goal,
        expected_return_rate,
    )


def calculate_wealth_creation_goal(
    target_corpus: float, years_to_goal: int, expected_return_rate: float
) -> Dict[str, Any]:
    return _calculate_standard_goal(
        "Wealth Creation",
        GoalType.WEALTH_CREATION,
        target_corpus,
        years_to_goal,
        expected_return_rate,
    )


def calculate_emergency_fund_goal(
    monthly_expenses: float,
    months_of_coverage: int = 6,
    expected_return_rate: float = 0.0,
) -> Dict[str, Any]:
    corpus = float(monthly_expenses) * max(0, int(months_of_coverage))
    return {
        "goal_name": "Emergency Fund",
        "goal_type": GoalType.EMERGENCY_FUND.value,
        "months_of_coverage": int(months_of_coverage),
        "future_corpus": round(corpus, 2),
        "required_sip": round(corpus / 12, 2) if corpus > 0 else 0.0,
        "expected_return_rate": float(expected_return_rate),
        "inflation_rate": INFLATION_MAPPING[GoalType.EMERGENCY_FUND],
    }


def calculate_goal_by_type(
    goal_type: str, payload: Dict[str, Any], expected_return_rate: float
) -> Dict[str, Any]:
    normalized = str(goal_type).strip().lower()
    present_cost = float(
        payload.get("present_cost", payload.get("target_amount", payload.get("cost", 0.0)))
    )
    years_to_goal = int(payload.get("years_to_goal", payload.get("years", 0)))

    if normalized == GoalType.RETIREMENT.value:
        return calculate_retirement_goal(
            current_age=int(payload["current_age"]),
            current_monthly_expense=float(payload["current_monthly_expense"]),
            expected_return_rate=expected_return_rate,
            retirement_age=int(payload.get("retirement_age", 60)),
            existing_corpus=float(payload.get("existing_corpus", 0.0)),
            post_retirement_income=payload.get("post_retirement_income"),
            post_retirement_years=int(payload.get("post_retirement_years", 25)),
            include_post_retirement_income=bool(
                payload.get("include_post_retirement_income", False)
            ),
        )
    if normalized == GoalType.CHILD_EDUCATION.value:
        return calculate_child_education_goal(
            present_cost=present_cost,
            years_to_goal=years_to_goal,
            expected_return_rate=expected_return_rate,
            current_age=payload.get("current_age"),
            child_age=payload.get("child_age"),
        )
    if normalized == GoalType.CHILD_MARRIAGE.value:
        return calculate_child_marriage_goal(
            present_cost, years_to_goal, expected_return_rate
        )
    if normalized == GoalType.HOUSE_PURCHASE.value:
        return calculate_house_purchase_goal(
            present_cost, years_to_goal, expected_return_rate
        )
    if normalized == GoalType.VEHICLE_PURCHASE.value:
        return calculate_vehicle_purchase_goal(
            present_cost, years_to_goal, expected_return_rate
        )
    if normalized == GoalType.VACATION.value:
        return calculate_vacation_goal(present_cost, years_to_goal, expected_return_rate)
    if normalized == GoalType.WEALTH_CREATION.value:
        return calculate_wealth_creation_goal(
            present_cost, years_to_goal, expected_return_rate
        )
    if normalized == GoalType.EMERGENCY_FUND.value:
        return calculate_emergency_fund_goal(
            monthly_expenses=float(payload.get("monthly_expenses", present_cost)),
            months_of_coverage=int(payload.get("months_of_coverage", 6)),
            expected_return_rate=expected_return_rate,
        )
    return calculate_custom_goal(
        goal_name=str(payload.get("goal_name", "Custom Goal")),
        present_cost=present_cost,
        years_to_goal=years_to_goal,
        expected_return_rate=expected_return_rate,
        goal_type=normalized or GoalType.CUSTOM.value,
        custom_inflation=payload.get("custom_inflation"),
    )
