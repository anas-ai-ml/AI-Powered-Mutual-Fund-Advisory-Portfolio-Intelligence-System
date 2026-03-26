from config import is_feature_enabled

if is_feature_enabled("advanced_goal_types", True):
    from backend.engines.v2.goal_engine import (
        GoalRegistry,
        GoalType,
        INFLATION_MAPPING,
        build_goal_sip_comparison,
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
