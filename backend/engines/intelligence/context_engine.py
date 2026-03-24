"""
context_engine.py
─────────────────
Generates a macro-economic context snapshot for the current market environment.

Design principles:
  • Works with ZERO external API calls — uses sensible Indian-market defaults.
  • Reads the existing backend/data/inflation_data.csv for inflation inputs.
  • Every value is configurable via keyword arguments, enabling future
    live-data integration as a simple drop-in.
  • Falls back to neutral defaults if anything fails.
  • Fully independent — no imports from any other engine.
"""

import os
import csv
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Default macro snapshot (India, 2026 baseline) ───────────────────────────
_DEFAULTS: Dict[str, Any] = {
    # Annualised CPI inflation (general) — read from CSV if available
    "inflation_rate": 0.06,
    # RBI repo rate (as of early 2026)
    "interest_rate": 0.065,
    # Geopolitical risk index: 0 = calm, 1 = extreme tension
    "geopolitical_risk": 0.20,
    # Market volatility index proxy (Nifty VIX scaled 0-1; ~15 VIX ≈ 0.25)
    "market_volatility": 0.25,
    # Broad commodity trend: "bullish" | "neutral" | "bearish"
    "commodity_trend": "neutral",
    # Interest rate environment: "rising" | "stable" | "falling"
    "interest_rate_trend": "stable",
    # Base prediction confidence coming from the internal models
    "base_confidence": 0.85,
}

# ── Inflation CSV path (relative to this file's package root) ────────────────
_CSV_PATH = os.path.join(
    os.path.dirname(__file__),       # backend/engines/intelligence/
    "..", "..",                       # backend/
    "data", "inflation_data.csv",
)


def _load_inflation_from_csv(csv_path: str) -> Optional[float]:
    """
    Read the 'general' inflation rate from inflation_data.csv.

    Returns the float rate if found, else None.
    """
    try:
        abs_path = os.path.abspath(csv_path)
        with open(abs_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("category", "").strip().lower() == "general":
                    return float(row["rate"].strip())
    except Exception as exc:
        logger.warning("context_engine: Could not read inflation CSV — %s", exc)
    return None


def _compute_inflation_impact(inflation_rate: float) -> float:
    """
    Translate an annualised inflation rate into a 0–1 impact score.

    Scale:
        ≤3%  → 0.0  (very low impact)
        6%   → 0.3  (moderate — RBI target band)
        10%  → 0.7  (high)
        ≥15% → 1.0  (extreme)
    """
    breakpoints = [(0.03, 0.0), (0.06, 0.3), (0.10, 0.7), (0.15, 1.0)]
    if inflation_rate <= breakpoints[0][0]:
        return 0.0
    if inflation_rate >= breakpoints[-1][0]:
        return 1.0
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if x0 <= inflation_rate <= x1:
            t = (inflation_rate - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 3)
    return 0.3  # safe fallback


def _build_explanation(
    inflation_impact: float,
    geopolitical_risk: float,
    market_volatility: float,
    adjusted_confidence: float,
    interest_rate_trend: str,
    commodity_trend: str,
) -> str:
    """
    Generate a plain-English explanation of the macro context adjustment.
    Avoids jargon; suitable for layperson display.
    """
    factors = []

    if inflation_impact > 0.5:
        factors.append("high inflation eroding purchasing power")
    elif inflation_impact > 0.2:
        factors.append("moderate inflation")

    if geopolitical_risk > 0.5:
        factors.append("significant geopolitical instability")
    elif geopolitical_risk > 0.2:
        factors.append("some geopolitical uncertainty")

    if market_volatility > 0.5:
        factors.append("elevated market volatility")
    elif market_volatility > 0.3:
        factors.append("moderate market swings")

    if interest_rate_trend == "rising":
        factors.append("rising interest rates")
    elif interest_rate_trend == "falling":
        factors.append("falling interest rates (positive for equities)")

    if commodity_trend == "bullish":
        factors.append("rising commodity prices")
    elif commodity_trend == "bearish":
        factors.append("falling commodity prices")

    if not factors:
        return (
            "The macro environment looks stable. Confidence is at its baseline level."
        )

    factor_str = ", ".join(factors)
    direction = "reduced" if adjusted_confidence < _DEFAULTS["base_confidence"] else "maintained"
    return (
        f"Prediction confidence {direction} due to: {factor_str}. "
        "These factors reflect the broader economic climate and may shift as conditions evolve."
    )


def get_macro_context(
    inflation_rate: Optional[float] = None,
    interest_rate: Optional[float] = None,
    geopolitical_risk: Optional[float] = None,
    market_volatility: Optional[float] = None,
    commodity_trend: Optional[str] = None,
    interest_rate_trend: Optional[str] = None,
    base_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute a macro-economic context snapshot and return an enriched dict.

    All parameters are **optional**. If not provided, sensible Indian-market
    defaults (or values from ``inflation_data.csv``) are used automatically.

    Parameters
    ----------
    inflation_rate : float, optional
        Annual CPI inflation rate as a decimal (e.g. 0.06 for 6%).
    interest_rate : float, optional
        Central bank policy rate as a decimal (e.g. 0.065 for 6.5%).
    geopolitical_risk : float, optional
        Geopolitical tension index in [0, 1].
    market_volatility : float, optional
        Market volatility proxy in [0, 1].
    commodity_trend : str, optional
        One of "bullish", "neutral", or "bearish".
    interest_rate_trend : str, optional
        One of "rising", "stable", or "falling".
    base_confidence : float, optional
        Baseline prediction confidence from internal models [0, 1].

    Returns
    -------
    Dict[str, Any]
        A dictionary with the following keys:

        * ``macro_context_score``  – overall stability score [0, 1]
        * ``inflation_impact``     – scaled inflation impact [0, 1]
        * ``geopolitical_risk``    – geopolitical tension [0, 1]
        * ``market_volatility``    – market volatility [0, 1]
        * ``interest_rate_trend``  – "rising" | "stable" | "falling"
        * ``commodity_trend``      – "bullish" | "neutral" | "bearish"
        * ``interest_rate``        – actual rate used
        * ``inflation_rate``       – actual rate used
        * ``adjusted_confidence``  – base_confidence adjusted for risk
        * ``explanation``          – plain-English summary for end users
    """
    try:
        # ── Resolve inputs (caller → CSV → hard default) ─────────────────
        csv_inflation = _load_inflation_from_csv(_CSV_PATH)

        inf_rate = inflation_rate if inflation_rate is not None else (
            csv_inflation if csv_inflation is not None else _DEFAULTS["inflation_rate"]
        )
        int_rate         = interest_rate       if interest_rate       is not None else _DEFAULTS["interest_rate"]
        geo_risk         = geopolitical_risk   if geopolitical_risk   is not None else _DEFAULTS["geopolitical_risk"]
        mkt_vol          = market_volatility   if market_volatility   is not None else _DEFAULTS["market_volatility"]
        com_trend        = commodity_trend     if commodity_trend     is not None else _DEFAULTS["commodity_trend"]
        int_trend        = interest_rate_trend if interest_rate_trend is not None else _DEFAULTS["interest_rate_trend"]
        base_conf        = base_confidence     if base_confidence     is not None else _DEFAULTS["base_confidence"]

        # ── Compute sub-scores ─────────────────────────────────────────────
        inflation_impact = _compute_inflation_impact(inf_rate)

        # Commodity bonus/penalty on volatility
        commodity_vol_adj = {"bullish": 0.05, "neutral": 0.0, "bearish": 0.05}.get(com_trend, 0.0)
        effective_vol = min(1.0, mkt_vol + commodity_vol_adj)

        # Interest rate effect: rising rates marginally increases risk
        rate_risk = {"rising": 0.10, "stable": 0.0, "falling": -0.05}.get(int_trend, 0.0)
        effective_geo_risk = max(0.0, min(1.0, geo_risk + rate_risk))

        # ── Composite risk factor (weighted average) ───────────────────────
        # Weights: inflation 35%, geopolitical 35%, volatility 30%
        composite_risk = round(
            (inflation_impact * 0.35)
            + (effective_geo_risk * 0.35)
            + (effective_vol * 0.30),
            3,
        )
        composite_risk = max(0.0, min(1.0, composite_risk))

        # ── Macro context score: inverse of composite risk ─────────────────
        macro_context_score = round(1.0 - composite_risk, 3)

        # ── Adjust prediction confidence ───────────────────────────────────
        # final_confidence = base_confidence × (1 − risk_factor)
        adjusted_confidence = round(base_conf * (1.0 - composite_risk), 3)
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

        # ── Build explanation ──────────────────────────────────────────────
        explanation = _build_explanation(
            inflation_impact, effective_geo_risk, effective_vol,
            adjusted_confidence, int_trend, com_trend,
        )

        return {
            "macro_context_score":  macro_context_score,
            "inflation_impact":     round(inflation_impact, 3),
            "geopolitical_risk":    round(effective_geo_risk, 3),
            "market_volatility":    round(effective_vol, 3),
            "interest_rate_trend":  int_trend,
            "commodity_trend":      com_trend,
            "interest_rate":        round(int_rate, 4),
            "inflation_rate":       round(inf_rate, 4),
            "adjusted_confidence":  adjusted_confidence,
            "explanation":          explanation,
        }

    except Exception as exc:
        logger.error("context_engine: Unexpected error — %s. Returning neutral defaults.", exc)
        return _neutral_defaults()


def _neutral_defaults() -> Dict[str, Any]:
    """Return a fully neutral context (used as fallback on any error)."""
    return {
        "macro_context_score":  1.0,
        "inflation_impact":     0.0,
        "geopolitical_risk":    0.0,
        "market_volatility":    0.0,
        "interest_rate_trend":  "stable",
        "commodity_trend":      "neutral",
        "interest_rate":        _DEFAULTS["interest_rate"],
        "inflation_rate":       _DEFAULTS["inflation_rate"],
        "adjusted_confidence":  _DEFAULTS["base_confidence"],
        "explanation":          "Macro environment data unavailable. Using neutral defaults.",
    }
