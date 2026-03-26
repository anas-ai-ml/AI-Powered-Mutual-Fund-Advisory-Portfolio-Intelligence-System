import json
import os

import numpy as np
from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Risk score band thresholds
# These boundaries are intentionally configurable (via a JSON file) while
# still living as a named constant for easy transparency.
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_RISK_BAND_THRESHOLDS: Dict[str, Dict[str, float]] = {
    # Conservative: 1.0 – 4.9 (±0.5 std dev around mean of low-risk profiles)
    "Conservative": {"min": 1.0, "max": 4.9},
    # Moderate: 5.0 – 7.4 (central tendency band)
    "Moderate": {"min": 5.0, "max": 7.4},
    # Aggressive: 7.5 – 10.0 (±0.5 std dev of high-risk profiles)
    "Aggressive": {"min": 7.5, "max": 10.0},
}


def _load_risk_band_thresholds() -> Dict[str, Dict[str, float]]:
    """
    Optionally override DEFAULT_RISK_BAND_THRESHOLDS from a config file.
    """
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "risk_band_thresholds.json"
    )
    config_path = os.path.abspath(config_path)
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Basic validation: must contain min/max for all 3 bands.
            for band in DEFAULT_RISK_BAND_THRESHOLDS.keys():
                if band not in loaded:
                    return DEFAULT_RISK_BAND_THRESHOLDS
                if "min" not in loaded[band] or "max" not in loaded[band]:
                    return DEFAULT_RISK_BAND_THRESHOLDS
            return loaded
    except Exception:
        # If config parsing fails, silently fall back to defaults.
        pass
    return DEFAULT_RISK_BAND_THRESHOLDS


# Named constant as requested (still overridable by config).
RISK_BAND_THRESHOLDS: Dict[str, Dict[str, float]] = _load_risk_band_thresholds()


class CalibrationEngine:
    def __init__(self):
        self.target_distribution = {
            "Conservative": (0, 30),
            "Moderate": (30, 70),
            "Aggressive": (70, 100),
        }
        self.score_bounds = (1.0, 10.0)

    def calibrate_score(self, raw_score, historical_scores=None):
        if historical_scores is not None and len(historical_scores) > 0:
            try:
                hist_mean = np.mean(historical_scores)
                hist_std = np.std(historical_scores)

                if hist_std > 0:
                    z_score = (raw_score - hist_mean) / hist_std
                    calibrated = 5.0 + z_score * 1.5
                else:
                    calibrated = raw_score
            except:
                calibrated = raw_score
        else:
            calibrated = raw_score

        return round(
            max(self.score_bounds[0], min(self.score_bounds[1], calibrated)), 2
        )

    def assign_category(self, calibrated_score):
        # Use band thresholds for clear, non-arbitrary scoring transparency.
        score = float(calibrated_score)
        for band, bounds in RISK_BAND_THRESHOLDS.items():
            if bounds["min"] <= score <= bounds["max"]:
                return band
        # Robust fallback on edge cases.
        if score < RISK_BAND_THRESHOLDS["Moderate"]["min"]:
            return "Conservative"
        if score < RISK_BAND_THRESHOLDS["Aggressive"]["min"]:
            return "Moderate"
        return "Aggressive"

    def get_risk_metrics(self, category):
        return {
            "Conservative": {"return": 8, "volatility": 6, "drawdown": 10},
            "Moderate": {"return": 12, "volatility": 12, "drawdown": 20},
            "Aggressive": {"return": 16, "volatility": 20, "drawdown": 35},
        }.get(category, {"return": 10, "volatility": 10, "drawdown": 15})

    def get_confidence_interval(self, score, historical_scores=None):
        if historical_scores is not None and len(historical_scores) > 10:
            std = np.std(historical_scores)
            return {
                "lower": round(max(1.0, score - 1.96 * std), 2),
                "upper": round(min(10.0, score + 1.96 * std), 2),
                "confidence": "high" if std < 1.5 else "medium" if std < 2.5 else "low",
            }
        return {
            "lower": round(score - 1.0, 2),
            "upper": round(score + 1.0, 2),
            "confidence": "low",
        }

    def apply_user_feedback(self, current_score, user_adjuster, historical_scores=None):
        adjusted = current_score + (user_adjuster - 5.0) * 0.5
        return self.calibrate_score(adjusted, historical_scores)
