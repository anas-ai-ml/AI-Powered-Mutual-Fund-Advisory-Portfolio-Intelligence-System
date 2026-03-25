import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2

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

TICKER_MAP = {
    "Equity - Large Cap": "^NSEI",
    "Equity - Mid Cap": "^NSEMDCP50",
    "Equity - Small Cap": "^CNXSC",
    "Equity - Flexi Cap": "^CNX100",
    "Equity - Sectoral": "^CNXIT",
    "Equity - Hybrid": "NIFTYBEES.NS",
    "Debt": "LIQUIDBEES.NS",
    "Gold": "GOLDBEES.NS",
}


def _retry_with_backoff(func, max_retries: int = MAX_RETRIES):
    """Decorator: retry with exponential backoff."""

    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = INITIAL_BACKOFF * (2**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed: {e}")
        raise last_error

    return wrapper


class MarketDataFetcher:
    def __init__(self, years_history: int = 5):
        self.years = years_history
        self.end_date = datetime.today()
        self.start_date = self.end_date - timedelta(days=365 * self.years)
        self.data_cache = pd.DataFrame()

    @_retry_with_backoff
    def fetch_data(self) -> pd.DataFrame:
        """Fetch monthly adjusted close prices for all proxy tickers."""
        tickers = list(TICKER_MAP.values())

        data = yf.download(
            tickers,
            start=self.start_date,
            end=self.end_date,
            interval="1d",
            progress=False,
            timeout=10,
        )

        if "Adj Close" in data:
            adj_close = data["Adj Close"]
        elif "Close" in data:
            adj_close = data["Close"]
        elif data.columns.nlevels > 1 and "Close" in data.columns.levels[0]:
            adj_close = data["Close"]
        else:
            adj_close = data

        adj_close = adj_close.resample("ME").last()

        adj_close = adj_close.dropna(axis=1, how="all").ffill()
        self.data_cache = adj_close
        return adj_close

    def get_data_with_fallback(self) -> pd.DataFrame:
        """Get market data with full fallback hierarchy."""
        try:
            data = self.fetch_data()
            if data is not None and not data.empty:
                logger.info("Successfully fetched live market data")
                return data
        except Exception as e:
            logger.warning(f"Live fetch failed: {e}")

        cached = self._load_from_cache()
        if cached is not None:
            logger.info("Using cached market data")
            return cached

        logger.warning("Using default market data (empty DataFrame)")
        return pd.DataFrame()

    def _load_from_cache(self) -> Optional[pd.DataFrame]:
        """Load data from file cache."""
        try:
            from data.cache.cache_manager import load_market_data_fallback

            cached = load_market_data_fallback()
            if cached and "data" in cached:
                return pd.DataFrame(cached["data"])
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
        return None

    def _save_to_cache(self, data: pd.DataFrame) -> None:
        """Save data to file cache."""
        try:
            from data.cache.cache_manager import save_market_data
            from data.cache.cache_manager import DEFAULT_MARKET_DATA

            stats = {
                k: DEFAULT_MARKET_DATA["stats"].get(
                    k, {"return": 0.10, "volatility": 0.15}
                )
                for k in TICKER_MAP.keys()
            }
            save_market_data(stats, pd.DataFrame())
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    def compute_statistics(self):
        """Compute annualized returns, volatility, and correlation matrix."""
        df = self.data_cache
        if df.empty:
            try:
                df = self.fetch_data()
            except Exception as e:
                logger.warning(f"Live fetch failed in compute_statistics: {e}")
                cached = self._load_from_cache()
                if cached is not None and not cached.empty:
                    df = cached

        if df.empty:
            logger.warning("Returning DEFAULT_ASSUMPTIONS (no live or cached data)")
            stats = DEFAULT_ASSUMPTIONS.copy()
            return stats, pd.DataFrame()

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
                compounded_return = (1 + series).prod() ** (
                    12 / max(1, len(series))
                ) - 1
                annual_volatility = series.std() * np.sqrt(12)

                # Sanity bounds
                compounded_return = np.clip(compounded_return, 0.05, 0.25)
                annual_volatility = np.clip(annual_volatility, 0.02, 0.40)

                stats[asset] = {
                    "return": round(compounded_return, 4),
                    "volatility": round(annual_volatility, 4),
                }
            else:
                stats[asset] = DEFAULT_ASSUMPTIONS[asset]

        # Compute correlation matrix based on monthly returns
        correlation_matrix = monthly_returns.corr()
        reverse_map = {v: k for k, v in TICKER_MAP.items()}
        correlation_matrix.rename(columns=reverse_map, index=reverse_map, inplace=True)

        assets = list(TICKER_MAP.keys())
        correlation_matrix = correlation_matrix.reindex(index=assets, columns=assets)
        correlation_matrix = correlation_matrix.fillna(0.0)
        np.fill_diagonal(correlation_matrix.values, 1.0)

        self._save_to_cache(df)

        return stats, correlation_matrix

    def save_computed_stats(self, filepath: str = None):
        stats, corr = self.compute_statistics()

        try:
            from data.cache.cache_manager import save_market_data

            save_market_data(stats, corr)
        except Exception as e:
            logger.warning(f"Failed to save to cache: {e}")

        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "live_assumptions.json")
        with open(filepath, "w") as f:
            json.dump(stats, f, indent=4)
        return stats


if __name__ == "__main__":
    fetcher = MarketDataFetcher()
    stats, corr = fetcher.compute_statistics()
    print("Computed Stats:", json.dumps(stats, indent=2))
    print("\nCorrelation Matrix:\n", corr)
