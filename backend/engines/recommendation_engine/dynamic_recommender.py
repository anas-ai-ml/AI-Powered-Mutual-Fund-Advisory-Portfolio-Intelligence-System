"""
backend/engines/recommendation_engine/dynamic_recommender.py
────────────────────────────────────────────────────────────
The core orchestrator for the new dynamic recommendation pipeline.
Loads data, filters, scores, diversifies, and explains.
"""

import os
import pandas as pd
import logging
from typing import Dict, Any, List

from .quality_filter import apply_quality_filter
from .scoring_engine import score_funds
from .user_matching import apply_user_matching

logger = logging.getLogger(__name__)

FUNDS_CSV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai_agents", "data", "mutual_funds.csv")
)

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
            
        # Diversification Rule: max 2 funds per category block.
        # Ensure we pick the absolute best scoring fund.
        top_fund = matched.iloc[0].to_dict()
        
        # 6. Explanation Engine & Confidence Calculation
        score = top_fund.get("score", 0.0)
        
        if score > 80: confidence = "High"
        elif score > 50: confidence = "Medium"
        else: confidence = "Low"
        
        vol_str = "low" if top_fund.get("volatility", 1) < 0.12 else "higher"
        
        # Base Explanation
        reason = f"Selected for strong multi-factor ranking (Score: {score:.1f}). "
        reason += f"It matches your {risk_profile} risk profile with consistent historical returns and {vol_str} volatility. "
        
        # Market Alignment Narrative
        trend = market_signals.get('market_trend', 'neutral')
        if trend == 'bearish' and ("large" in top_fund.get('category','').lower() or "debt" in top_fund.get('category','').lower()):
            reason += "Current market conditions are bearish, making this defensive posture highly ideal."
        elif trend == 'bullish' and ("small" in top_fund.get('category','').lower() or "mid" in top_fund.get('category','').lower()):
            reason += "Bullish market momentum provides strong upside capture for this category."
        elif "debt" in top_fund.get('category','').lower():
            reason += "Provides excellent capital preservation against market fluctuations."
            
        recommendations.append({
            "name": top_fund.get("scheme_name", "Unknown Fund"),
            "category": top_fund.get("category", "N/A"),
            "risk": risk_profile,
            "allocation_weight": weight,
            "1y": top_fund.get("1y", 0.0),
            "3y": top_fund.get("3y", 0.0),
            "5y": top_fund.get("5y", 0.0),
            "score": score,
            "confidence": confidence,
            "reason": reason,
            "nav": top_fund.get("nav", 0.0), # legacy support
            "date": top_fund.get("date", "N/A"), # legacy support
            "volatility": top_fund.get("volatility", 0.0), # legacy support
            "sharpe": top_fund.get("sharpe", 0.0) # legacy support
        })

    return recommendations
