import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

# Default fallbacks if live data fetching fails
DEFAULT_ASSUMPTIONS = {
    "Equity - Large Cap": {"return": 0.13, "volatility": 0.15},
    "Equity - Mid Cap": {"return": 0.15, "volatility": 0.20},
    "Equity - Small Cap": {"return": 0.17, "volatility": 0.25},
    "Equity - Flexi Cap": {"return": 0.14, "volatility": 0.18},
    "Equity - Sectoral": {"return": 0.16, "volatility": 0.22},
    "Equity - Hybrid": {"return": 0.11, "volatility": 0.12},
    "Debt": {"return": 0.075, "volatility": 0.04},
    "Gold": {"return": 0.09, "volatility": 0.15},
}

# Proxy tickers on Yahoo Finance for Indian Markets
TICKER_MAP = {
    "Equity - Large Cap": "^NSEI",          # Nifty 50
    "Equity - Mid Cap": "^NSEMDCP50",       # Nifty Midcap 50
    "Equity - Small Cap": "^CNXSC",         # Nifty Smallcap 100
    "Equity - Flexi Cap": "^CNX100",        # Nifty 100 as proxy
    "Equity - Sectoral": "^CNXIT",          # Nifty IT as standard sectoral proxy
    "Equity - Hybrid": "NIFTYBEES.NS",      # Proxy for blending (using ETF)
    "Debt": "LIQUIDBEES.NS",                # Liquid ETF proxy for debt
    "Gold": "GOLDBEES.NS"                   # Gold ETF
}

class MarketDataFetcher:
    def __init__(self, years_history: int = 5):
        self.years = years_history
        self.end_date = datetime.today()
        self.start_date = self.end_date - timedelta(days=365 * self.years)
        self.data_cache = pd.DataFrame()

    def fetch_data(self) -> pd.DataFrame:
        """Fetch monthly adjusted close prices for all proxy tickers."""
        tickers = list(TICKER_MAP.values())
        try:
            # Download DAILY data (more reliable)
            data = yf.download(tickers, start=self.start_date, end=self.end_date, interval="1d", progress=False)
            
            # Safely extract close prices
            if "Adj Close" in data:
                adj_close = data["Adj Close"]
            elif "Close" in data:
                adj_close = data["Close"]
            elif data.columns.nlevels > 1 and "Close" in data.columns.levels[0]:
                adj_close = data["Close"] 
            else:
                adj_close = data
                
            # Resample to monthly (last business day of month)
            adj_close = adj_close.resample('M').last()
            
            # Forward fill missing values then drop completely dead columns
            adj_close = adj_close.dropna(axis=1, how="all").ffill()
            self.data_cache = adj_close
            return adj_close
        except Exception as e:
            print(f"Warning: Failed to fetch live market data. Using default assumptions. Error: {e}")
            return pd.DataFrame()

    def compute_statistics(self):
        """Compute annualized returns, volatility, and correlation matrix."""
        df = self.data_cache
        if df.empty:
            df = self.fetch_data()

        if df.empty:
            # Return fallbacks
            stats = {k: {"return": v["return"], "volatility": v["volatility"]} for k, v in DEFAULT_ASSUMPTIONS.items()}
            return stats, pd.DataFrame() # Empty correlation matrix fallback

        # Calculate monthly returns
        # Handle NA by dropping columns that are completely NA, then fill the rest
        df = df.dropna(axis=1, how="all").ffill().bfill()
        monthly_returns = df.pct_change().dropna(how="all")
        
        # Annualize returns (CAGR) and volatility
        stats = {}
        for asset, ticker in TICKER_MAP.items():
            if ticker in monthly_returns.columns and not monthly_returns[ticker].empty:
                series = monthly_returns[ticker].dropna()
                if len(series) < 12:
                    stats[asset] = DEFAULT_ASSUMPTIONS[asset]
                    continue
                # Geometric mean for CAGR
                compounded_return = (1 + series).prod() ** (12 / max(1, len(series))) - 1
                annual_volatility = series.std() * np.sqrt(12)
                
                # Sanity bounds
                compounded_return = np.clip(compounded_return, 0.05, 0.25)
                annual_volatility = np.clip(annual_volatility, 0.02, 0.40)
                
                stats[asset] = {
                    "return": round(compounded_return, 4),
                    "volatility": round(annual_volatility, 4)
                }
            else:
                stats[asset] = DEFAULT_ASSUMPTIONS[asset]

        # Compute correlation matrix based on monthly returns
        correlation_matrix = monthly_returns.corr()
        # Rename columns/index from tickers to asset classes
        reverse_map = {v: k for k, v in TICKER_MAP.items()}
        correlation_matrix.rename(columns=reverse_map, index=reverse_map, inplace=True)

        # Force perfect alignment with `stats.keys()` so matrix multiplication doesn't scramble!
        assets = list(TICKER_MAP.keys())
        correlation_matrix = correlation_matrix.reindex(index=assets, columns=assets)
        # Fill missing with 0 (no correlation fallback)
        correlation_matrix = correlation_matrix.fillna(0.0)
        np.fill_diagonal(correlation_matrix.values, 1.0)

        return stats, correlation_matrix

    def save_computed_stats(self, filepath: str = None):
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "live_assumptions.json")
        stats, _ = self.compute_statistics()
        with open(filepath, "w") as f:
            json.dump(stats, f, indent=4)
        return stats

if __name__ == "__main__":
    fetcher = MarketDataFetcher()
    stats, corr = fetcher.compute_statistics()
    print("Computed Stats:", json.dumps(stats, indent=2))
    print("\nCorrelation Matrix:\n", corr)
