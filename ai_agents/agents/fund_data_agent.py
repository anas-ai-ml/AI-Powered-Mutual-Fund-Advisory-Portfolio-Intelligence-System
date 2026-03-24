"""
ai_agents/agents/fund_data_agent.py
───────────────────────────────────
Data Ingestion Agent for Mutual Funds.
Responsible for maintaining an always up-to-date dataset of the fund universe.
Fetches real AMFI data via ai_layer and enriches it with metrics required
for the quality filter (expense ratio, AUM, etc).
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime
import os

from backend.data.mutual_fund_api import get_mutual_fund_universe
from backend.engines.fund_categorizer import categorize_funds
from backend.engines.fund_performance_engine import apply_performance_metrics

logger = logging.getLogger(__name__)

# Constants
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
FUNDS_DATA_FILE = os.path.join(DATA_DIR, "mutual_funds.csv")

class FundDataAgent:
    @staticmethod
    def run() -> dict:
        """
        Fetch the latest mutual fund universe, enrich with fundamentals, and persist.
        Returns a meta-dictionary about the sync.
        """
        logger.info("[FundDataAgent] Initiating daily fund data sync...")
        
        # 1. Fetch live AMFI NAVs and map to categories
        df, is_live = get_mutual_fund_universe()
        if df is None or df.empty:
            logger.error("Failed to fetch mutual fund universe.")
            return {"status": "error", "message": "Failed to fetch universe"}
        
        # Categorize to get 'category' column
        df = categorize_funds(df)
        
        # 2. Derive simulated fundamentals mimicking Moneycontrol data
        # In a fully productionized web-scraping setup, this would be scraped.
        # Here we simulate true-to-life realistic parameters per AMC size.
        np.random.seed(42)  # For reproducible simulation
        
        # AMCs with large systemic AUM generally
        large_amcs = ["SBI", "HDFC", "ICICI", "Nippon", "Kotak", "Axis"]
        
        def assign_aum(scheme: str) -> float:
            is_large = any(amc in str(scheme).upper() for amc in large_amcs)
            # AUM in Crores
            if is_large:
                return round(np.random.uniform(10000, 80000), 2)
            return round(np.random.uniform(100, 5000), 2)
            
        def assign_expense_ratio(category: str) -> float:
            # Different categories have different average ERs
            category = str(category).lower()
            if "debt" in category or "liquid" in category:
                return round(np.random.uniform(0.1, 0.8), 2)
            elif "index" in category or "etf" in category:
                return round(np.random.uniform(0.05, 0.4), 2)
            else:
                return round(np.random.uniform(0.5, 2.5), 2)

        df["aum_crore"] = df["scheme_name"].apply(assign_aum)
        df["expense_ratio"] = df["category"].apply(assign_expense_ratio)
        
        # 3. Enhance with 1y, 3y, 5y returns and volatility
        # Using the existing performace engine mapping logic (simulated from index proxies over AMFI)
        df = apply_performance_metrics(df)
        
        # Ensure all required features are present
        required_cols = ["scheme_name", "category", "1y", "3y", "5y", "volatility", "aum_crore", "expense_ratio"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0 if col != "category" else "Unknown"
        
        # Determine explicit risk category based on category & volatility
        def assign_risk(row) -> str:
            cat = str(row["category"]).lower()
            if "debt" in cat or "liquid" in cat:
                return "low"
            elif row["volatility"] < 0.12:
                return "moderate"
            else:
                return "high"
                
        df["risk"] = df.apply(assign_risk, axis=1)
        
        # 4. Save to CSV
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(FUNDS_DATA_FILE, index=False)
        
        logger.info(f"[FundDataAgent] Successfully synced {len(df)} funds to {FUNDS_DATA_FILE}")
        
        return {
            "status": "success",
            "funds_count": len(df),
            "timestamp": datetime.now().isoformat(),
            "is_live_amfi": is_live
        }

# Singleton instance
agent = FundDataAgent()

if __name__ == "__main__":
    result = agent.run()
    print(result)
