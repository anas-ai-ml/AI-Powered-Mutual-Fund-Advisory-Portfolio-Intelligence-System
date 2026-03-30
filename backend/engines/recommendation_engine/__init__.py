"""
backend/engines/recommendation_engine/__init__.py
────────────────────────────────────────────────
Public surface of the recommendation_engine package.
Exports suggest_mutual_funds so the rest of the app keeps the same import:
    from backend.engines.recommendation_engine import suggest_mutual_funds
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from backend.engines.advanced_products_engine import (
    get_advanced_product_eligibility,
    recommend_bonds,
)
from backend.data.mutual_fund_api import get_mutual_fund_universe
from backend.engines.fund_categorizer import categorize_funds
from backend.engines.fund_performance_engine import apply_performance_metrics
from .dynamic_recommender import run_dynamic_pipeline

logger = logging.getLogger(__name__)


def get_processed_fund_universe() -> tuple[pd.DataFrame, bool]:
    df, is_live = get_mutual_fund_universe()
    if df is not None and not df.empty:
        df = categorize_funds(df)
        df = apply_performance_metrics(df)
    return df, is_live


def _get_signals_with_fallback() -> Dict[str, Any]:
    """Get market signals with full fallback hierarchy."""
    try:
        from ai_agents.db import storage

        latest_intelligence = storage.get_latest()
        if (
            latest_intelligence
            and "signals" in latest_intelligence
            and latest_intelligence["signals"]
        ):
            signals = latest_intelligence["signals"]
            logger.info("[RecommendEngine] Using LIVE market signals.")
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
    allocation: Dict[str, Any],
    risk_profile: str,
    user_profile: Optional[Dict[str, Any]] = None,
    goals: Optional[List[Dict[str, Any]]] = None,
    monte_carlo_prob: float = 0.0,
) -> tuple[Any, bool]:
    """
    Suggests specific mutual funds dynamically using the Multi-Factor
    Automatic Recommendation Engine.

    When ``user_profile`` is provided the advisory pipeline runs first:
    - If the client fails safety guardrails (no life cover, no emergency fund,
      negative net worth, etc.) a BLOCKED sentinel dict is returned and no
      funds are generated.
    - If the client is eligible the guardrail-adjusted allocation from the
      orchestrator replaces the raw ``allocation`` input before fund selection.

    Backward-compatible: callers that do not pass ``user_profile`` get the
    original behaviour unchanged.
    """
    effective_allocation = dict(allocation or {})

    if user_profile is not None:
        try:
            from backend.core.advisory_orchestrator import run_advisory_pipeline

            advisory_result = run_advisory_pipeline(
                user_profile=user_profile,
                goals=goals,
                monte_carlo_prob=monte_carlo_prob,
                allocation_input=effective_allocation,
            )
            status = advisory_result.get("status", "")
            if status == "BLOCKED":
                logger.warning(
                    "[RecommendEngine] Advisory BLOCKED — %s",
                    advisory_result.get("reason", ""),
                )
                return {
                    "status": "BLOCKED",
                    "reason": advisory_result.get("reason", ""),
                    "priority_actions": advisory_result.get("priority_actions", []),
                    "investment_allowed": False,
                    "financial_health": advisory_result.get("financial_health", {}),
                    "decision_trace": advisory_result.get("decision_trace", []),
                }, False
            # Use guardrail-adjusted allocation for fund selection
            guardrailed = advisory_result.get("allocation")
            if isinstance(guardrailed, dict) and guardrailed.get("status") != "LOCKED":
                effective_allocation = guardrailed
                logger.info("[RecommendEngine] Using guardrail-adjusted allocation.")
        except Exception as exc:
            logger.error("[RecommendEngine] Advisory pipeline error: %s", exc)
            # Fall through to normal recommendation path on error

    signals = _get_signals_with_fallback()

    recommendations = run_dynamic_pipeline(
        allocation_weights=effective_allocation,
        risk_profile=risk_profile,
        market_signals=signals,
    )

    is_live = len(recommendations) > 0
    return recommendations, is_live


def suggest_advanced_products(
    allocation: Dict[str, Any],
    annual_income: float,
    net_worth: float,
) -> Dict[str, Any]:
    bond_weight = float(allocation.get("Bonds", 0.0))
    return {
        "bonds": recommend_bonds(target_weight=bond_weight),
        "eligibility_cards": get_advanced_product_eligibility(
            annual_income=annual_income,
            net_worth=net_worth,
        ),
    }
