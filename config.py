FEATURE_FLAGS = {
    "v2_risk_explanation": True,
    "advanced_goal_types": True,
    "investment_mode_recommendation": True,
    "advanced_products": False,
}

EXCLUDE_ETF_FROM_ADVISORY = True


def is_feature_enabled(flag_name: str, default: bool = False) -> bool:
    return bool(FEATURE_FLAGS.get(flag_name, default))
