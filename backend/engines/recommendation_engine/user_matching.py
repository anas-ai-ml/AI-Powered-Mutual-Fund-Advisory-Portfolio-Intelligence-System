"""
backend/engines/recommendation_engine/user_matching.py
──────────────────────────────────────────────────────
Align recommendations strictly with user risk appetite.
"""

import pandas as pd

def apply_user_matching(df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    Filter the fund universe to strictly match the user's overall risk profile.
    Penalize mismatches heavily if they happen to squeak by category matching.
    """
    if df.empty:
        return df
        
    risk_level = risk_profile.lower()
    
    # Ensure all funds conform to the user risk bounding
    # LOW risk: allow only debt, hybrid, large_cap
    # MODERATE risk: allow large, flexi, index
    # HIGH risk: mid, small, thematic
    
    allowed_categories = set()
    penalized_categories = set()
    
    if "conservative" in risk_level or "low" in risk_level:
        allowed_categories = {"debt", "hybrid", "liquid", "large cap"}
        penalized_categories = {"small cap", "mid cap", "sectoral", "thematic"}
    elif "moderate" in risk_level:
        allowed_categories = {"large cap", "flexi", "multi cap", "hybrid", "debt"}
        penalized_categories = {"small cap", "sectoral"}
    elif "aggressive" in risk_level or "high" in risk_level:
        # Aggressive users can buy anything, but prioritize alpha
        allowed_categories = set() # empty set means no restriction
        pass
        
    def check_match(row) -> bool:
        cat = str(row.get("category", "")).lower()
        
        # Hard exclusions
        for p in penalized_categories:
            if p in cat:
                return False
                
        # If specific allowed categories exist, check them
        if allowed_categories:
            matches = any(a in cat for a in allowed_categories)
            if not matches:
                return False
                
        return True

    matched_mask = df.apply(check_match, axis=1)
    df = df[matched_mask].copy()
    
    return df
