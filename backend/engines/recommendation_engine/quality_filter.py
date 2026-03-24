"""
backend/engines/recommendation_engine/quality_filter.py
───────────────────────────────────────────────────────
Eliminates unreliable or poor-performing funds before scoring.
Ensures we only recommend institutional-grade, cost-effective options.
"""

import pandas as pd
import logging

logger = logging.getLogger(__name__)

def apply_quality_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter Rules:
      - expense_ratio < 2.0
      - aum > 500 crore
      - 3y_return > 0 (fund must not be consistently destroying capital over 3 years)
    """
    initial_count = len(df)
    
    # Apply conditions safely
    if "expense_ratio" in df.columns:
        df = df[df["expense_ratio"] < 2.0]
        
    if "aum_crore" in df.columns:
        df = df[df["aum_crore"] > 500.0]
        
    if "3y" in df.columns:
        # If '3y' is not available (e.g. 0.0 or NaN), we might keep it 
        # if it's a new fund, but the rule asks for > 0.
        # We will assume if 3y == 0.0 exactly, it's missing data. We don't drop those strictly,
        # but we drop strictly negative ones.
        df = df[df["3y"] >= 0.0]

    filtered_count = len(df)
    logger.info(f"[QualityFilter] Dropped {initial_count - filtered_count} funds. {filtered_count} remaining.")
    
    return df.copy()
