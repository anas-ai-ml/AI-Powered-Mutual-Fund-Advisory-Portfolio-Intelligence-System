from typing import Any, Dict


def validate_user_profile(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(user_profile or {})
    required_fields = [
        "life_cover",
        "health_cover",
        "monthly_income",
        "existing_corpus",
        "total_liabilities",
    ]

    for field in required_fields:
        if field not in sanitized:
            raise ValueError(f"Missing required field: {field}")

    for key in ["life_cover", "health_cover", "monthly_income"]:
        sanitized[key] = max(float(sanitized.get(key, 0.0) or 0.0), 0.0)

    return sanitized
