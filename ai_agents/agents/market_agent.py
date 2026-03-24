"""
ai_agents/agents/market_agent.py
────────────────────────────────
Continuously fetch real-time financial data.
Wraps ai_layer.data_ingestion for use in the Celery pipeline.
"""

import logging
from typing import Any, Dict

from ai_layer.data_ingestion.market_data import get_market_snapshot
from ai_layer.data_ingestion.macro_data import get_macro_indicators

logger = logging.getLogger(__name__)

class MarketAgent:
    @staticmethod
    def run() -> Dict[str, Any]:
        """
        Fetch real-time market and macro data synchronously.
        This is called by the Celery worker.
        """
        logger.info("[MarketAgent] Fetching live market and macro data...")
        
        # We fetch fresh data here directly (bypassing the internal ai_layer cache
        # which is used by the frontend).
        market_snapshot = get_market_snapshot()
        macro_indicators = get_macro_indicators()
        
        return {
            "market_snapshot": market_snapshot,
            "macro_indicators": macro_indicators,
            "agent_version": "1.0",
        }

# Singleton instance
agent = MarketAgent()
