"""
ai_layer/data_ingestion/market_data.py
──────────────────────────────────────
Fetches real-time market data for the key instruments needed by the
AI Layer signal and decision engines.

Data is fetched via yfinance (already a project dependency).
Every fetch is wrapped in a try/except so a single ticker failure
never blocks the rest of the pipeline.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)

# ── Instrument configuration ─────────────────────────────────────────────────
INSTRUMENTS: Dict[str, str] = {
    "nifty":   "^NSEI",       # Nifty 50
    "sensex":  "^BSESN",      # BSE Sensex
    "vix":     "^INDIAVIX",   # India VIX
    "sp500":   "^GSPC",       # S&P 500
    "crude":   "CL=F",        # Crude Oil (WTI)
    "usdinr":  "INR=X",       # USD-INR exchange rate
}

# Hardcoded fallback last-known values (updated periodically)
_FALLBACKS: Dict[str, Dict[str, Any]] = {
    "nifty":  {"price": 22500.0, "change_pct": 0.0, "dma_50": 22000.0,  "dma_200": 21500.0},
    "sensex": {"price": 74000.0, "change_pct": 0.0, "dma_50": 72000.0,  "dma_200": 70000.0},
    "vix":    {"price": 15.0,    "change_pct": 0.0, "dma_50": 15.0,     "dma_200": 15.0},
    "sp500":  {"price": 5200.0,  "change_pct": 0.0, "dma_50": 5100.0,   "dma_200": 4900.0},
    "crude":  {"price": 85.0,    "change_pct": 0.0, "dma_50": 83.0,     "dma_200": 80.0},
    "usdinr": {"price": 83.5,    "change_pct": 0.0, "dma_50": 83.0,     "dma_200": 82.5},
}


def _fetch_instrument(key: str, ticker: str) -> Dict[str, Any]:
    """
    Download 200 days of daily data for one ticker and compute:
      - current price
      - daily change %
      - 50-day moving average
      - 200-day moving average

    Returns a dict. Falls back to _FALLBACKS on any error.
    """
    try:
        end = datetime.today()
        start = end - timedelta(days=210)  # A bit extra to ensure 200 trading days

        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )

        if df is None or df.empty or len(df) < 5:
            logger.warning("market_data: No data for %s (%s) — using fallback", key, ticker)
            return {**_FALLBACKS[key], "source": "fallback", "ticker": ticker}

        # Extract close series (handles MultiIndex from yfinance ≥0.2.38)
        if hasattr(df.columns, "levels"):
            close = df["Close"].squeeze()
        else:
            close = df["Close"].squeeze()

        close = close.dropna()

        if len(close) < 5:
            return {**_FALLBACKS[key], "source": "fallback", "ticker": ticker}

        price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2]) if len(close) >= 2 else price
        change_pct = round(((price - prev_price) / prev_price) * 100, 2) if prev_price != 0 else 0.0

        dma_50 = round(float(close.tail(50).mean()), 2) if len(close) >= 50 else round(float(close.mean()), 2)
        dma_200 = round(float(close.tail(200).mean()), 2) if len(close) >= 200 else dma_50

        return {
            "price":      round(price, 2),
            "change_pct": change_pct,
            "dma_50":     dma_50,
            "dma_200":    dma_200,
            "source":     "live",
            "ticker":     ticker,
            "as_of":      str(close.index[-1].date()),
        }

    except Exception as exc:
        logger.error("market_data: Error fetching %s (%s): %s", key, ticker, exc)
        return {**_FALLBACKS[key], "source": "fallback", "ticker": ticker}


def get_market_snapshot() -> Dict[str, Any]:
    """
    Fetch a real-time snapshot for all configured instruments.

    Returns
    -------
    dict
        Keys: ``nifty``, ``sensex``, ``vix``, ``sp500``, ``crude``, ``usdinr``.
        Each value contains: ``price``, ``change_pct``, ``dma_50``, ``dma_200``,
        ``source`` ("live" or "fallback"), ``ticker``, ``as_of``.

    Example
    -------
    >>> snap = get_market_snapshot()
    >>> snap["nifty"]["price"]
    22847.35
    """
    snapshot: Dict[str, Any] = {}
    live_count = 0

    for key, ticker in INSTRUMENTS.items():
        data = _fetch_instrument(key, ticker)
        snapshot[key] = data
        if data.get("source") == "live":
            live_count += 1

    snapshot["_meta"] = {
        "fetched_at":  datetime.now().isoformat(timespec="seconds"),
        "live_count":  live_count,
        "total_count": len(INSTRUMENTS),
        "is_fully_live": live_count == len(INSTRUMENTS),
    }

    logger.info(
        "market_data: snapshot ready — %d/%d live", live_count, len(INSTRUMENTS)
    )
    return snapshot
