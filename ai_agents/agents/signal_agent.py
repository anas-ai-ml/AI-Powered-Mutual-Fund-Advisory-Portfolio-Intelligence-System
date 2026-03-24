"""
ai_agents/agents/signal_agent.py
────────────────────────────────
Convert raw data into interpretable market signals.
Wraps ai_layer.signal_engine for use in the Celery pipeline.
"""

import logging
from typing import Any, Dict

from ai_layer.signal_engine.market_signals import generate_signals

logger = logging.getLogger(__name__)

class SignalAgent:
    @staticmethod
    def run(market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes raw market and macro data, outputs actionable signals.
        """
        logger.info("[SignalAgent] Generating market signals...")
        
        market_snapshot = market_data.get("market_snapshot", {})
        macro_indicators = market_data.get("macro_indicators", {})
        
        signals = generate_signals(market_snapshot, macro_indicators)
        signals["agent_version"] = "1.0"
        
        return signals

# Singleton instance
agent = SignalAgent()
