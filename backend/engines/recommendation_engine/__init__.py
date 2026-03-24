"""
backend/engines/recommendation_engine/__init__.py
─────────────────────────────────────────────────
Public surface of the recommendation_engine package.
Exports suggest_mutual_funds so the rest of the app keeps the same import:
    from backend.engines.recommendation_engine import suggest_mutual_funds
"""
import logging
from typing import Any, Dict, List

from .dynamic_recommender import run_dynamic_pipeline

logger = logging.getLogger(__name__)


def suggest_mutual_funds(
    allocation: Dict[str, Any], risk_profile: str
) -> tuple[List[Dict[str, Any]], bool]:
    """
    Suggests specific mutual funds dynamically using the new Multi-Factor
    Automatic Recommendation Engine.
    """
    # 1. Fetch live market signals from the AI Agents storage cache
    try:
        from ai_agents.db import storage
        latest_intelligence = storage.get_latest()
        if latest_intelligence and "signals" in latest_intelligence:
            signals = latest_intelligence["signals"]
            logger.info("[RecommendEngine] Using LIVE market signals.")
        else:
            raise ValueError("No signals in cache")
    except Exception:
        signals = {
            "market_trend": "neutral",
            "volatility": "medium",
            "global_sentiment": "neutral",
        }
        logger.warning("[RecommendEngine] Cache miss. Using NEUTRAL market signals.")

    # 2. Run the dynamic pipeline
    recommendations = run_dynamic_pipeline(
        allocation_weights=allocation,
        risk_profile=risk_profile,
        market_signals=signals,
    )

    is_live = len(recommendations) > 0
    return recommendations, is_live
