from typing import Any


def safe_round(value: Any, decimals: int = 2) -> float:
    try:
        return round(float(value), decimals)
    except Exception:
        return 0.0


def clamp(value: Any, low: float, high: float) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = low
    return max(low, min(high, numeric))
