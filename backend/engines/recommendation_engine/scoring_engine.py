"""
backend/engines/recommendation_engine/scoring_engine.py
───────────────────────────────────────────────────────
Multi-factor scoring engine to rank funds and adjust for market signals.
"""

import pandas as pd
from typing import Dict, Any

def score_funds(df: pd.DataFrame, signals: Dict[str, Any]) -> pd.DataFrame:
    """
    Apply multi-factor scoring and market-aware adjustments.
    Filters:
     - 0.25 * 1Y
     - 0.25 * 3Y
     - 0.20 * 5Y
     - 0.15 * Consistency
     - 0.15 * Market fit
    """
    if df.empty:
        return df
        
    df = df.copy()

    # 1. Feature Engineering: Consistency Score
    # Lower volatility = higher consistency
    # Adding 1.0 to avoid division by zero
    if "volatility" in df.columns:
        df["consistency_score"] = 1.0 / (df["volatility"] + 1.0)
    else:
        df["consistency_score"] = 0.5
        
    # Standardize / Normalize performance metrics to [0, 1] range roughly for uniform weighting
    # We clip returns to a standard max to prevent outliers dominating
    def normalize(series: pd.Series, max_val: float) -> pd.Series:
        clipped = series.clip(0, max_val)
        return clipped / max_val if max_val > 0 else 0

    n_1y = normalize(df.get("1y", pd.Series(0, index=df.index)), 0.60)
    n_3y = normalize(df.get("3y", pd.Series(0, index=df.index)), 0.40)
    n_5y = normalize(df.get("5y", pd.Series(0, index=df.index)), 0.25)
    
    # 2. Market Fit Score
    market_trend = signals.get("market_trend", "neutral").lower()
    market_volatility = signals.get("volatility", "medium").lower()

    def calculate_market_fit(row) -> float:
        cat = str(row.get("category", "")).lower()
        fit = 0.5  # Base neutral fit (50%)
        
        # Trend adjustments
        if market_trend == "bearish":
            if "large cap" in cat: fit += 0.3
            if "small cap" in cat: fit -= 0.3
            if "mid cap" in cat: fit -= 0.1
        elif market_trend == "bullish":
            if "flexi" in cat: fit += 0.2
            if "mid cap" in cat: fit += 0.2
            if "small cap" in cat: fit += 0.3
            if "debt" in cat: fit -= 0.2

        # Volatility adjustments
        if market_volatility == "high":
            if "debt" in cat or "hybrid" in cat: fit += 0.3
            if "equity" in cat or "small cap" in cat: fit -= 0.2
            
        return max(0.0, min(1.0, fit)) # clamp between 0 and 1
        
    df["market_fit"] = df.apply(calculate_market_fit, axis=1)
    
    # 3. Final Multi-Factor Score (0 to 100)
    df["score"] = (
        (0.25 * n_1y) +
        (0.25 * n_3y) +
        (0.20 * n_5y) +
        (0.15 * df["consistency_score"]) +
        (0.15 * df["market_fit"])
    ) * 100.0
    
    df["score"] = df["score"].fillna(0).round(2)
    
    return df
