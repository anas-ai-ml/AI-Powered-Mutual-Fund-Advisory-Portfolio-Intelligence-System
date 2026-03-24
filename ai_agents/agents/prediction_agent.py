"""
ai_agents/agents/prediction_agent.py
────────────────────────────────────
Estimate market direction and expected return ranges probabilistically.
This module introduces net-new predictive logic on top of the ai_layer signals.
Designed to be easily hot-swappable with an ML model in the future.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class PredictionAgent:
    @staticmethod
    def run(signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule-based probabilistic prediction.
        
        Returns
        -------
        dict
            direction, confidence, expected_return (low, mid, high)
        """
        logger.info("[PredictionAgent] Generating probabilistic market directions...")
        
        market_trend = signals.get("market_trend", "neutral")
        volatility = signals.get("volatility", "medium")
        sentiment = signals.get("global_sentiment", "neutral")
        inflation = signals.get("inflation_trend", "stable")
        repo_rate = signals.get("repo_rate_pct", 6.5)
        
        # ── Base confidence calculation ──────────────────────────────────────────
        confidence = 0.60  # baseline structural confidence in Indian markets
        
        if market_trend == "bullish":
            confidence += 0.10
        elif market_trend == "bearish":
            confidence -= 0.05
            
        if volatility == "high":
            confidence -= 0.10
        elif volatility == "low":
            confidence += 0.05
            
        if sentiment == "negative":
            confidence -= 0.05
        elif sentiment == "positive":
            confidence += 0.05
            
        if inflation == "stable":
            confidence += 0.05
        elif inflation == "rising":
            confidence -= 0.05
            
        # Clamp confidence [0.0, 1.0]
        confidence = round(max(0.01, min(0.99, confidence)), 3)
        
        # ── Directionality ───────────────────────────────────────────────────────
        direction = "up" if confidence > 0.55 else "down"
        
        # ── Expected Returns (Probabilistic Bands for Equities) ──────────────────
        # Low scenario: Base fixed income return loosely tied to repo rate
        low_band = round(repo_rate + 1.0, 1)
        
        # Mid scenario: Scaled by confidence levels (historical average ~12-14%)
        # Max confidence approaches ~18%, min approaches ~2%
        mid_band = round(confidence * 20.0, 1)
        if mid_band < low_band:
            mid_band = low_band + 2.0
            
        # High scenario: Upside capturing beta dynamics
        vol_penalty = 1.0 if volatility == "high" else (0.5 if volatility == "medium" else 0.0)
        high_band = round(mid_band + (1.0 - vol_penalty) * 8.0 + 2.0, 1)
        
        return {
            "direction": direction,
            "confidence": confidence,
            "expected_return": {
                "low_pct": low_band,
                "mid_pct": mid_band,
                "high_pct": high_band,
            },
            "agent_version": "1.0",
        }

# Singleton instance
agent = PredictionAgent()
