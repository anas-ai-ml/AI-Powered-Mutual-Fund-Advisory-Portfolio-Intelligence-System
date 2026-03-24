"""
ai_agents/agents/decision_agent.py
──────────────────────────────────
Dynamically adjust portfolio allocation.
Wraps ai_layer.decision_engine.adaptive_allocation for Celery.
"""

import logging
from typing import Any, Dict

from ai_layer.decision_engine.adaptive_allocation import apply_adaptive_allocation

logger = logging.getLogger(__name__)

# Base MPT (from an external profile, static here for demonstration of the agent pipe)
# In reality, this could be passed along in the pipeline.
_BASE_ALLOCATION = {
    "Equity - Large Cap": 50.0,
    "Debt":               35.0,
    "Gold":               15.0,
}

class DecisionAgent:
    @staticmethod
    def run(signals: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically adjust the base portfolio based on live signals.
        """
        logger.info("[DecisionAgent] Adjusting portfolio allocation...")
        
        # apply_adaptive_allocation from ai_layer natively scales the deltas
        # and guarantees total sum == 100%.
        adjusted = apply_adaptive_allocation(_BASE_ALLOCATION, signals)
        
        return {
            "adaptive_allocation": adjusted.get("adaptive_allocation"),
            "base_allocation": _BASE_ALLOCATION,
            "adjustments": {
                "equity_delta": adjusted.get("equity_delta", 0.0),
                "debt_delta": adjusted.get("debt_delta", 0.0),
                "gold_delta": adjusted.get("gold_delta", 0.0),
            },
            "reasons": adjusted.get("adjustment_reasons", []),
            "agent_version": "1.0",
        }

# Singleton instance
agent = DecisionAgent()
