"""
ai_layer/signal_engine/market_signals.py
─────────────────────────────────────────
Converts raw market snapshot + macro indicators into interpretable
signals that the decision engine consumes.

All logic is pure (no I/O) — takes dicts, returns dicts.
"""

from typing import Any, Dict


# ── VIX thresholds (India VIX calibrated) ────────────────────────────────────
_VIX_LOW    = 13.0
_VIX_HIGH   = 20.0

# ── S&P 500 & crude oil sentiment threshold (daily change) ───────────────────
_SP500_BEAR_CHANGE = -1.0   # More than 1% drop == negative sentiment
_CRUDE_BULL_CHANGE =  1.5   # Crude up >1.5% day == inflationary pressure


def classify_volatility(vix_price: float) -> str:
    """
    Classify market volatility from India VIX level.

    Parameters
    ----------
    vix_price : float
        Current India VIX index level.

    Returns
    -------
    str  "low" | "medium" | "high"
    """
    if vix_price < _VIX_LOW:
        return "low"
    elif vix_price <= _VIX_HIGH:
        return "medium"
    else:
        return "high"


def classify_trend(dma_50: float, dma_200: float) -> str:
    """
    Golden-Cross / Death-Cross signal based on 50 vs 200 DMA.

    Returns "bullish" if 50DMA > 200DMA, else "bearish".
    """
    return "bullish" if dma_50 > dma_200 else "bearish"


def classify_global_sentiment(
    sp500_change_pct: float,
    crude_change_pct: float,
) -> str:
    """
    Derive a global market sentiment signal from S&P 500 and crude oil
    daily changes.

    Logic:
      - Both positive                    → "positive"
      - S&P negative OR crude very high  → "negative"
      - Otherwise                        → "neutral"
    """
    sp_negative = sp500_change_pct < _SP500_BEAR_CHANGE
    crude_inflationary = crude_change_pct > _CRUDE_BULL_CHANGE

    if not sp_negative and not crude_inflationary:
        if sp500_change_pct > 0.5:
            return "positive"
        return "neutral"

    if sp_negative or crude_inflationary:
        return "negative"
    return "neutral"


def classify_usdinr_pressure(usdinr_change_pct: float) -> str:
    """
    Signal from USD-INR movement.
    Rising USD-INR (INR weakening) is negative for imports/inflation.
    """
    if usdinr_change_pct > 0.3:
        return "inr_weakening"
    elif usdinr_change_pct < -0.3:
        return "inr_strengthening"
    return "stable"


def generate_signals(
    market_snapshot: Dict[str, Any],
    macro_indicators: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate the full set of market signals from raw data.

    Parameters
    ----------
    market_snapshot : dict
        Output of ``market_data.get_market_snapshot()``.
    macro_indicators : dict
        Output of ``macro_data.get_macro_indicators()``.

    Returns
    -------
    dict
        ``market_trend``        – "bullish" | "bearish"
        ``volatility``          – "low" | "medium" | "high"
        ``inflation_trend``     – "rising" | "stable" | "falling"
        ``interest_rate_trend`` – "rising" | "stable" | "falling"
        ``global_sentiment``    – "positive" | "neutral" | "negative"
        ``usdinr_pressure``     – "inr_weakening" | "stable" | "inr_strengthening"
        ``golden_cross``        – True | False (50DMA > 200DMA on Nifty)
        ``vix_level``           – actual VIX value (float)
        ``cpi_yoy_pct``         – CPI YoY % (float)
        ``repo_rate_pct``       – RBI repo rate % (float)
        ``signal_source``       – "live" | "partial" | "fallback"
    """
    nifty = market_snapshot.get("nifty", {})
    vix   = market_snapshot.get("vix",   {})
    sp500 = market_snapshot.get("sp500", {})
    crude = market_snapshot.get("crude", {})
    usdinr = market_snapshot.get("usdinr", {})

    # ── Market trend (Golden Cross on Nifty 50) ──────────────────────────────
    dma_50  = nifty.get("dma_50",  22000.0)
    dma_200 = nifty.get("dma_200", 21500.0)
    market_trend = classify_trend(dma_50, dma_200)
    golden_cross = dma_50 > dma_200

    # ── Volatility from VIX ──────────────────────────────────────────────────
    vix_level = vix.get("price", 15.0)
    volatility = classify_volatility(vix_level)

    # ── Global sentiment ─────────────────────────────────────────────────────
    global_sentiment = classify_global_sentiment(
        sp500.get("change_pct", 0.0),
        crude.get("change_pct", 0.0),
    )

    # ── USD-INR pressure ─────────────────────────────────────────────────────
    usdinr_pressure = classify_usdinr_pressure(usdinr.get("change_pct", 0.0))

    # ── Macro signals (passed through from macro_data) ───────────────────────
    inflation_trend = macro_indicators.get("inflation_trend", "stable")
    rate_trend      = macro_indicators.get("rate_trend",      "stable")
    cpi_yoy         = macro_indicators.get("cpi_yoy_pct",     6.0)
    repo_rate       = macro_indicators.get("repo_rate_pct",   6.5)

    # ── Source quality ───────────────────────────────────────────────────────
    mkt_source   = market_snapshot.get("_meta", {}).get("is_fully_live", False)
    macro_source = macro_indicators.get("source", "fallback")
    if mkt_source and macro_source == "live":
        signal_source = "live"
    elif mkt_source or macro_source in ("live", "partial"):
        signal_source = "partial"
    else:
        signal_source = "fallback"

    return {
        "market_trend":        market_trend,
        "volatility":          volatility,
        "inflation_trend":     inflation_trend,
        "interest_rate_trend": rate_trend,
        "global_sentiment":    global_sentiment,
        "usdinr_pressure":     usdinr_pressure,
        "golden_cross":        golden_cross,
        "vix_level":           round(vix_level, 2),
        "cpi_yoy_pct":         round(cpi_yoy, 2),
        "repo_rate_pct":       round(repo_rate, 2),
        "nifty_price":         nifty.get("price", 0.0),
        "nifty_change_pct":    nifty.get("change_pct", 0.0),
        "usdinr_price":        usdinr.get("price", 83.5),
        "crude_price":         crude.get("price", 85.0),
        "signal_source":       signal_source,
    }
