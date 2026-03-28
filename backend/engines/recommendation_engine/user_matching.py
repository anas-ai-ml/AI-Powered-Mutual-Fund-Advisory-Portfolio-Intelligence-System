"""
backend/engines/recommendation_engine/user_matching.py
──────────────────────────────────────────────────────
Align recommendations strictly with user risk appetite.
"""

import pandas as pd

def apply_user_matching(df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    if df.empty:
        return df

    risk_level = risk_profile.lower()
    df = df.copy()

    # Score multiplier per category based on risk profile
    def risk_multiplier(row) -> float:
        cat = str(row.get("category", "")).lower()
        if "conservative" in risk_level:
            if any(x in cat for x in ["debt", "liquid", "hybrid", "large cap"]):
                return 1.0
            if any(x in cat for x in ["small cap", "mid cap", "sectoral", "thematic"]):
                return 0.0
            return 0.5
        elif "moderate" in risk_level:
            if any(x in cat for x in ["small cap", "sectoral", "thematic"]):
                return 0.4
            if any(x in cat for x in ["large cap", "flexi", "hybrid", "multi cap"]):
                return 1.0
            return 0.8
        elif "aggressive" in risk_level:
            if any(x in cat for x in ["debt", "liquid"]):
                return 0.3
            if any(x in cat for x in ["small cap", "mid cap", "flexi", "sectoral"]):
                return 1.2
            return 1.0
        return 1.0

    df["risk_multiplier"] = df.apply(risk_multiplier, axis=1)
    df = df[df["risk_multiplier"] > 0].copy()
    if "score" in df.columns:
        df["score"] = (df["score"] * df["risk_multiplier"]).round(2)
    return df.drop(columns=["risk_multiplier"])
