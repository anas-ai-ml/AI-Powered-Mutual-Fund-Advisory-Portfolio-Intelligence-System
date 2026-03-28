from config import is_feature_enabled

if is_feature_enabled("advanced_goal_types", True):
    from backend.engines.v2.goal_engine import (
        GOAL_CONFIGS,
        GoalConfig,
        GoalRegistry,
        GoalType,
        INFLATION_MAPPING,
        build_goal_sip_comparison,
        calculate_goal,
        calculate_child_education_goal,
        calculate_custom_goal,
        calculate_emergency_fund_goal,
        calculate_goal_by_type,
        calculate_goal_with_sip_topup,
        calculate_required_step_up_sip,
        calculate_house_purchase_goal,
        calculate_retirement_goal,
        calculate_sip_topup,
        calculate_vacation_goal,
        calculate_vehicle_purchase_goal,
        calculate_wealth_creation_goal,
        get_goal_registry,
        validate_goal_inputs,
    )
else:
    from dataclasses import dataclass, field

    from backend.engines.v1.goal_engine import (
        GoalRegistry,
        GoalType,
        INFLATION_MAPPING,
        build_goal_sip_comparison,
        calculate_child_education_goal,
        calculate_custom_goal,
        calculate_goal_with_sip_topup,
        calculate_required_step_up_sip,
        calculate_retirement_goal,
        calculate_sip_topup,
        get_goal_registry,
        validate_goal_inputs,
    )

    @dataclass(frozen=True)
    class GoalConfig:
        label: str
        required_inputs: list[str]
        description: str = ""
        optional_inputs: list[str] = field(default_factory=list)

    GOAL_CONFIGS = {
        GoalType.RETIREMENT.value: GoalConfig(
            label="Retirement",
            required_inputs=["current_monthly_expense", "retirement_age"],
            optional_inputs=[
                "include_post_retirement_income",
                "post_retirement_income",
                "post_retirement_years",
            ],
        ),
        GoalType.CHILD_EDUCATION.value: GoalConfig(
            label="Child Education",
            required_inputs=["target_amount", "years_to_goal"],
        ),
        GoalType.CUSTOM.value: GoalConfig(
            label="Custom Goal",
            required_inputs=["goal_name", "target_amount", "years_to_goal"],
            optional_inputs=["custom_inflation"],
        ),
    }

    def calculate_goal(goal_type: str, payload: dict, expected_return_rate: float) -> dict:
        normalized = str(goal_type).strip().lower()
        annual_sip_step_up = float(payload.get("annual_sip_step_up", 0.0) or 0.0)
        if normalized == GoalType.RETIREMENT.value:
            return calculate_retirement_goal(
                current_age=int(payload["current_age"]),
                current_monthly_expense=float(payload["current_monthly_expense"]),
                expected_return_rate=expected_return_rate,
                retirement_age=int(payload.get("retirement_age", 60)),
                existing_corpus=float(payload.get("existing_corpus", 0.0)),
                annual_sip_step_up=annual_sip_step_up,
            )
        if normalized == GoalType.CHILD_EDUCATION.value:
            return calculate_child_education_goal(
                present_cost=float(
                    payload.get(
                        "present_cost",
                        payload.get("target_amount", payload.get("cost", 0.0)),
                    )
                ),
                years_to_goal=int(payload.get("years_to_goal", payload.get("years", 0))),
                expected_return_rate=expected_return_rate,
                current_age=payload.get("current_age"),
                child_age=payload.get("child_age"),
                annual_sip_step_up=annual_sip_step_up,
            )
        result = calculate_custom_goal(
            goal_name=str(payload.get("goal_name", "Custom Goal")),
            present_cost=float(
                payload.get(
                    "present_cost",
                    payload.get("target_amount", payload.get("cost", 0.0)),
                )
            ),
            years_to_goal=int(payload.get("years_to_goal", payload.get("years", 0))),
            expected_return_rate=expected_return_rate,
            goal_type=normalized or GoalType.CUSTOM.value,
            custom_inflation=payload.get("custom_inflation"),
        )
        return calculate_goal_with_sip_topup(result, annual_sip_step_up)
