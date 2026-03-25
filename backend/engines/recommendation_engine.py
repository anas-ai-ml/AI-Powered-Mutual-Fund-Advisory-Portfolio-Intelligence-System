import streamlit as st
import pandas as pd
from typing import Dict, Any, List
import hashlib
from backend.data.mutual_fund_api import get_mutual_fund_universe
from backend.engines.fund_categorizer import categorize_funds
from backend.engines.fund_performance_engine import apply_performance_metrics


@st.cache_data(ttl=3600, show_spinner="Processing fund universe...")
def get_processed_fund_universe() -> tuple[pd.DataFrame, bool]:
    """Fetch, categorize, and score the full mutual fund universe."""
    df, is_live = get_mutual_fund_universe()
    if df is not None and not df.empty:
        df = categorize_funds(df)
        df = apply_performance_metrics(df)
    return df, is_live


from backend.engines.recommendation_engine.dynamic_recommender import (
    run_dynamic_pipeline,
)
from ai_agents.db import storage
import logging

logger = logging.getLogger(__name__)


def _get_signals_with_fallback() -> Dict[str, Any]:
    """Get market signals with full fallback hierarchy."""
    try:
        latest_intelligence = storage.get_latest()
        if (
            latest_intelligence
            and "signals" in latest_intelligence
            and latest_intelligence["signals"]
        ):
            signals = latest_intelligence["signals"]
            logger.info(
                "[RecommendEngine] Using LIVE market signals for dynamic adjustments."
            )
            try:
                from data.cache.cache_manager import save_signals

                save_signals(signals)
            except Exception:
                pass
            return signals
    except Exception as e:
        logger.warning(f"[RecommendEngine] Storage fetch failed: {e}")

    try:
        from data.cache.cache_manager import load_signals_fallback

        cached_signals = load_signals_fallback()
        if cached_signals and cached_signals.get("signal_source") != "fallback":
            logger.info("[RecommendEngine] Using CACHED market signals.")
            return cached_signals
    except Exception as e:
        logger.warning(f"[RecommendEngine] Cache fallback failed: {e}")

    logger.warning("[RecommendEngine] Using DEFAULT market signals (last resort).")
    return {
        "market_trend": "neutral",
        "volatility": "medium",
        "global_sentiment": "neutral",
        "inflation_trend": "stable",
        "interest_rate_trend": "stable",
        "signal_source": "fallback",
    }


def suggest_mutual_funds(
    allocation: Dict[str, Any], risk_profile: str
) -> tuple[List[Dict[str, Any]], bool]:
    """
    Suggests specific mutual funds dynamically using the new Multi-Factor
    Automatic Recommendation Engine.
    """

    signals = _get_signals_with_fallback()

    recommendations = run_dynamic_pipeline(
        allocation_weights=allocation, risk_profile=risk_profile, market_signals=signals
    )

    is_live = len(recommendations) > 0

    return recommendations, is_live
