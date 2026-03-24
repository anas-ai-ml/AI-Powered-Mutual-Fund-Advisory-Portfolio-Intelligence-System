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


from backend.engines.recommendation_engine.dynamic_recommender import run_dynamic_pipeline
from ai_agents.db import storage
import logging

logger = logging.getLogger(__name__)

def suggest_mutual_funds(
    allocation: Dict[str, Any], risk_profile: str
) -> tuple[List[Dict[str, Any]], bool]:
    """
    Suggests specific mutual funds dynamically using the new Multi-Factor
    Automatic Recommendation Engine.
    """
    
    # 1. Fetch live market signals from the AI Agents storage cache
    latest_intelligence = storage.get_latest()
    if latest_intelligence and "signals" in latest_intelligence:
        signals = latest_intelligence["signals"]
        logger.info("[RecommendEngine] Using LIVE market signals for dynamic adjustments.")
    else:
        signals = {
            "market_trend": "neutral",
            "volatility": "medium",
            "global_sentiment": "neutral"
        }
        logger.warning("[RecommendEngine] Cache miss. Using NEUTRAL market signals.")
        
    # 2. Run the dynamic pipeline
    recommendations = run_dynamic_pipeline(
        allocation_weights=allocation,
        risk_profile=risk_profile,
        market_signals=signals
    )
    
    # Check if the AMFI feed was considered "live" just for frontend display purposes.
    # In the new architecture, we assume True if we got recommendations since 
    # the Celery beat updates it continuously.
    is_live = len(recommendations) > 0
    
    return recommendations, is_live
