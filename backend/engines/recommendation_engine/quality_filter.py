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
    Hard rejection rules applied BEFORE scoring.  A fund must pass every
    applicable rule to remain in the investable universe.

    Rules:
      - expense_ratio  < 2.0   (cost threshold)
      - aum_crore      > 500   (liquidity / institutional grade)
      - 3y             > 0     (no capital destruction over 3 years)
      - alpha_3y       > 0     (must generate positive alpha vs benchmark)
      - information_ratio > 0  (active management must add value)
    """
    initial_count = len(df)

    if "expense_ratio" in df.columns:
        df = df[df["expense_ratio"] < 2.0]

    if "aum_crore" in df.columns:
        df = df[df["aum_crore"] > 500.0]

    if "3y" in df.columns:
        # Strictly positive 3-year return required; zero treated as no data → reject
        df = df[df["3y"] > 0.0]

    if "alpha_3y" in df.columns:
        # Funds must generate positive alpha; NaN rows are excluded
        df = df[df["alpha_3y"].notna() & (df["alpha_3y"] > 0.0)]

    if "information_ratio" in df.columns:
        # Positive information ratio confirms active management adds value
        df = df[df["information_ratio"].notna() & (df["information_ratio"] > 0.0)]

    filtered_count = len(df)
    logger.info(
        "[QualityFilter] Dropped %d funds. %d remaining after all quality gates.",
        initial_count - filtered_count,
        filtered_count,
    )

    return df.copy()
