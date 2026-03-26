import pandas as pd
import yfinance as yf
import numpy as np
import streamlit as st
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ETF Mapping
CATEGORY_PROXIES = {
    "Large Cap": "NIFTYBEES.NS",
    "Mid Cap": "MID150BEES.NS",
    "Small Cap": "JUNIORBEES.NS",
    "Flexi": "NIFTYBEES.NS",  # Fallback to Large Cap proxy
    "Hybrid": "NIFTYBEES.NS",  # Simple fallback, or a blended proxy if needed
    "Debt": "LIQUIDBEES.NS",
    "Gold": "GOLDBEES.NS",
    "Sectoral": "MID150BEES.NS",  # Fallback mapping
}

RISK_FREE_RATE = 0.06  # 6% India Risk-free rate


@st.cache_data(ttl=21600)  # Cache ETF proxy calculations for 6 hours
def get_category_performance() -> dict:
    """
    Fetches historical data for the proxy ETFs using yfinance and computes
    the 1Y, 3Y, 5Y CAGR, Volatility, and Sharpe Ratios.
    Returns a dictionary mapping of Category -> Performance Metrics
    """
    logger.info("Computing category performance using ETF proxies")

    end_date = datetime.today()
    start_date = end_date - timedelta(days=365 * 5 + 30)  # Fetch slightly over 5 years

    category_metrics = {}

    for category, ticker in CATEGORY_PROXIES.items():
        try:
            # Download historical closing prices
            df = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
            )

            if df.empty:
                logger.warning(f"No data found for proxy {ticker} ({category})")
                continue

            # Use 'Adj Close' if available, otherwise 'Close'
            price_col = "Adj Close" if "Adj Close" in df.columns else "Close"

            # Ensure price series is somewhat clean
            prices = df[price_col].dropna()

            if len(prices) < 252:  # Need at least ~1 year of data
                continue

            current_price = float(np.ravel(prices.iloc[-1])[0])

            # Utility to get price N years ago safely
            def get_historical_price(years_ago: int):
                target_date = end_date - timedelta(days=365 * years_ago)
                closest_date = prices.index.asof(target_date)
                if pd.isna(closest_date):
                    return None
                return float(np.ravel(prices.loc[closest_date])[0])

            p_1y = get_historical_price(1)
            p_3y = get_historical_price(3)
            p_5y = get_historical_price(5)

            cagr_1y = ((current_price / p_1y) ** (1 / 1) - 1) * 100 if p_1y else 0.0
            cagr_3y = (
                ((current_price / p_3y) ** (1 / 3) - 1) * 100 if p_3y else cagr_1y
            )  # fallback if short history
            cagr_5y = (
                ((current_price / p_5y) ** (1 / 5) - 1) * 100 if p_5y else cagr_3y
            )  # fallback

            # Daily Returns
            daily_returns = prices.pct_change().dropna()

            # Annualized Volatility (assuming 252 trading days)
            annual_volatility = float(daily_returns.std() * np.sqrt(252)) * 100

            # Sharpe Ratio
            if annual_volatility > 0:
                sharpe_ratio = (cagr_3y - (RISK_FREE_RATE * 100)) / annual_volatility
            else:
                sharpe_ratio = 0.0

            category_metrics[category] = {
                "1y": round(cagr_1y, 2),
                "3y": round(cagr_3y, 2),
                "5y": round(cagr_5y, 2),
                "volatility": round(annual_volatility, 2),
                "sharpe": round(sharpe_ratio, 2),
            }

        except Exception as e:
            logger.error(f"Failed to compute metrics for {ticker} ({category}): {e}")

    return category_metrics


def apply_performance_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the proxy historical metrics to the mutual fund universe.
    Calculates the final ranking score.
    Final Score = (CAGR_3Y x 0.40) + (CAGR_5Y x 0.30) + (Sharpe x 0.20) - (Volatility x 0.10)
    """
    if df is None or df.empty or "category" not in df.columns:
        return df

    metrics = get_category_performance()

    # Apply metrics
    df["1y"] = df["category"].apply(lambda x: metrics.get(x, {}).get("1y", 0.0))
    df["3y"] = df["category"].apply(lambda x: metrics.get(x, {}).get("3y", 0.0))
    df["5y"] = df["category"].apply(lambda x: metrics.get(x, {}).get("5y", 0.0))
    df["volatility"] = df["category"].apply(
        lambda x: metrics.get(x, {}).get("volatility", 0.0)
    )
    df["sharpe"] = df["category"].apply(lambda x: metrics.get(x, {}).get("sharpe", 0.0))

    # Calculate Ranking Score
    df["ranking_score"] = (
        (df["3y"] * 0.40)
        + (df["5y"] * 0.30)
        + (df["sharpe"] * 0.20)
        - (df["volatility"] * 0.10)
    )

    # Sort descending by ranking score
    df = df.sort_values(by="ranking_score", ascending=False)

    return df
