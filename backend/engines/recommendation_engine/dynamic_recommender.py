"""
backend/engines/recommendation_engine/dynamic_recommender.py
────────────────────────────────────────────────────────────
The core orchestrator for the new dynamic recommendation pipeline.
Loads data, filters, scores, diversifies, and explains.

AI BOUNDARY ENFORCEMENT
───────────────────────
This module is DETERMINISTIC.  Pipeline steps — loading, quality filtering,
scoring, risk-matching, and diversification — must remain free of LLM or
AI inference calls.

Permitted in this module:
  - Rule-based pipeline orchestration
  - Deterministic fund selection and diversification logic
  - String-based explanation generation from fund attributes

Not permitted in this module:
  - LLM-generated fund rankings or scores
  - Dynamic weighting driven by AI model outputs

AI is reserved exclusively for generating explanations, summaries, and
user-facing wording — never for filtering, scoring, or decision logic.
"""

# AI_BOUNDARY_ENFORCED — do not remove this marker
AI_BOUNDARY_ENFORCED: bool = True

import os
import pandas as pd
import logging
from typing import Dict, Any, List

from config import EXCLUDE_ETF_FROM_ADVISORY
from backend.data.benchmark_indices import enrich_with_benchmark_metrics, infer_fund_type
from .quality_filter import apply_quality_filter
from .scoring_engine import score_funds
from .user_matching import apply_user_matching

logger = logging.getLogger(__name__)

FUNDS_CSV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai_agents", "data", "mutual_funds.csv")
)


def _market_fit_reason(category: str, risk_profile: str, market_signals: Dict[str, Any]) -> str:
    trend = str(market_signals.get("market_trend", "neutral")).lower()
    volatility = str(market_signals.get("volatility", "medium")).lower()
    category_lower = str(category).lower()

    if volatility == "high" and ("large cap" in category_lower or "debt" in category_lower):
        return "Large-cap preferred as volatility is elevated, limiting drawdown risk."
    if trend == "bullish" and ("mid cap" in category_lower or "small cap" in category_lower):
        return "Bullish market momentum supports higher-beta categories for upside capture now."
    if "gold" in category_lower:
        return "Gold exposure is timely as a hedge against macro and inflation shocks."
    if "debt" in category_lower:
        return "Debt exposure is timely while capital preservation matters more than chasing peak returns."
    return f"{category} exposure fits the current market regime for your {risk_profile.lower()} profile."

def run_dynamic_pipeline(
    allocation_weights: Dict[str, float],
    risk_profile: str,
    market_signals: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    1. Load Fund Universe
    2. Quality Filter
    3. Multi-Factor Scoring with Market Adjustments
    4. User Risk Matching
    5. Diversification
    6. Generate Explanations
    """
    
    # 1. Load Data
    try:
        if not os.path.exists(FUNDS_CSV_PATH):
            logger.warning("mutual_funds.csv not found! Did the fund_data_agent run?")
            return []
        df = pd.read_csv(FUNDS_CSV_PATH)
    except Exception as e:
        logger.error(f"Failed to load fund universe: {e}")
        return []

    df = df.copy()
    df["fund_type"] = df["scheme_name"].apply(infer_fund_type)
    if EXCLUDE_ETF_FROM_ADVISORY:
        df = df[df["fund_type"] != "ETF"].copy()

    # 2. Quality Filter (Drop bad funds)
    df = apply_quality_filter(df)
    
    # 3. Score Funds (With Market Awareness)
    df = score_funds(df, market_signals)
    
    # 4. Filter by User Risk strictly
    df = apply_user_matching(df, risk_profile)
    
    if df.empty:
        logger.warning(f"No funds survived filtering for risk: {risk_profile}")
        return []

    # 5. Diversification Engine & Allocation Mapping
    # Match the MPT desired asset classes (Equity - Large Cap, Debt, Gold) to dataset categories
    recommendations = []
    
    # Sort the global dataframe by score highest first
    df = df.sort_values(by="score", ascending=False)
    
    for asset_class, weight in allocation_weights.items():
        if weight <= 0:
            continue
            
        target_cats = set()
        ac_lower = asset_class.lower()
        if "equity" in ac_lower:
            if "large cap" in ac_lower: target_cats = {"Large Cap"}
            elif "flexi" in ac_lower: target_cats = {"Flexi"}
            elif "small" in ac_lower: target_cats = {"Small Cap"}
            elif "mid" in ac_lower: target_cats = {"Mid Cap"}
            elif "hybrid" in ac_lower: target_cats = {"Hybrid"}
            else: target_cats = {"Large Cap", "Flexi"}
        elif "debt" in ac_lower:
            target_cats = {"Debt", "Liquid"}
        elif "gold" in ac_lower:
            target_cats = {"Gold", "Commodity"}

        matched = df[df["category"].str.lower().apply(lambda x: any(t.lower() in x for t in target_cats))]
        
        if matched.empty:
            continue
            
        # Pick top fund BUT vary selection slightly by risk profile
        # to ensure different profiles get different recommendations
        if "aggressive" in risk_profile.lower():
            # For aggressive: prioritize highest score (alpha-seeking)
            top_fund = matched.sort_values("score", ascending=False).iloc[0].to_dict()
        elif "conservative" in risk_profile.lower():
            # For conservative: prioritize consistency over raw score
            matched = matched.copy()
            matched["conservative_rank"] = (
                matched["score"] * 0.4
                + matched["consistency_score"].fillna(0.5) * 100 * 0.6
            )
            top_fund = matched.sort_values("conservative_rank", ascending=False).iloc[0].to_dict()
        else:
            # Moderate: balanced sort
            top_fund = matched.sort_values("score", ascending=False).iloc[0].to_dict()
        
        # 6. Explanation Engine & Confidence Calculation
        score = top_fund.get("score", 0.0)
        
        if score > 80: confidence = "High"
        elif score > 50: confidence = "Medium"
        else: confidence = "Low"
        
        vol_str = "low" if top_fund.get("volatility", 1) < 0.12 else "higher"
        
        market_reason = _market_fit_reason(
            top_fund.get("category", ""), risk_profile, market_signals
        )

        recommendation = {
            "name": top_fund.get("scheme_name", "Unknown Fund"),
            "category": top_fund.get("category", "N/A"),
            "risk": risk_profile,
            "allocation_weight": weight,
            "1y": top_fund.get("1y", 0.0),
            "3y": top_fund.get("3y", 0.0),
            "5y": top_fund.get("5y", 0.0),
            "score": score,
            "confidence": confidence,
            "reason": (
                f"Selected for strong multi-factor ranking (Score: {score:.1f}). "
                f"It matches your {risk_profile} risk profile with consistent historical returns and {vol_str} volatility. "
                f"{market_reason}"
            ),
            "nav": top_fund.get("nav", 0.0), # legacy support
            "date": top_fund.get("date", "N/A"), # legacy support
            "volatility": top_fund.get("volatility", 0.0), # legacy support
            "sharpe": top_fund.get("sharpe", 0.0), # legacy support
            "fund_type": top_fund.get("fund_type", infer_fund_type(top_fund.get("scheme_name", ""))),
            "market_reason": market_reason,
            "market_fit_reason": market_reason,
        }
        recommendations.append(enrich_with_benchmark_metrics(recommendation))

    return recommendations
