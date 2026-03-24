"""
ai_layer/scoring_engine/fund_scoring.py
────────────────────────────────────────
Market-aware mutual fund scoring engine.

Score formula:
    Score = (0.30 × 1Y_return)
           + (0.30 × 3Y_return)
           + (0.20 × consistency)       ← inverse of volatility, normalised
           + (0.20 × market_fit_score)  ← dynamic, based on current signals

market_fit_score logic:
    bearish   → large-cap + debt get +0.20 bonus
    bullish   → mid-cap + flexi get +0.20 bonus
    high_vol  → debt + gold get +0.15 bonus
    rising_inf→ equity categories get +0.10 (inflation hedge)

Returns a ranked list of funds with score and ai_reason.
"""

import logging
from copy import deepcopy
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ── Category metadata for fit scoring ────────────────────────────────────────
# Each entry: "favoured_in" conditions → bonus weight
_CATEGORY_FIT: Dict[str, Dict[str, float]] = {
    "Large Cap":  {"bearish": 0.20, "high_vol": 0.15, "rising_rates": 0.10},
    "Debt":       {"bearish": 0.20, "high_vol": 0.15, "falling_rates": 0.20},
    "Gold":       {"bearish": 0.10, "high_vol": 0.15, "rising_inf": 0.15, "negative_global": 0.10},
    "Mid Cap":    {"bullish": 0.20, "low_vol": 0.10},
    "Small Cap":  {"bullish": 0.15, "low_vol": 0.05},
    "Flexi":      {"bullish": 0.20, "medium_vol": 0.10},
    "Hybrid":     {"medium_vol": 0.10, "stable_rates": 0.05},
    "Sectoral":   {"bullish": 0.10},
}


def _compute_market_fit_score(category: str, signals: Dict[str, Any]) -> float:
    """
    Compute a 0–1 market-fit score for a fund category given current signals.

    Bonuses are additive, capped at 1.0.
    """
    fit_map = _CATEGORY_FIT.get(category, {})
    if not fit_map:
        return 0.50  # neutral for unknown categories

    base = 0.50
    bonus = 0.0

    trend = signals.get("market_trend", "bullish")
    vol   = signals.get("volatility", "medium")
    inf   = signals.get("inflation_trend", "stable")
    rates = signals.get("interest_rate_trend", "stable")
    sent  = signals.get("global_sentiment", "neutral")

    # Active conditions from signals
    active: Dict[str, bool] = {
        "bullish":        trend == "bullish",
        "bearish":        trend == "bearish",
        "low_vol":        vol == "low",
        "medium_vol":     vol == "medium",
        "high_vol":       vol == "high",
        "rising_inf":     inf == "rising",
        "rising_rates":   rates == "rising",
        "falling_rates":  rates == "falling",
        "stable_rates":   rates == "stable",
        "negative_global": sent == "negative",
    }

    for condition, weight in fit_map.items():
        if active.get(condition, False):
            bonus += weight

    return round(min(1.0, base + bonus), 3)


def _compute_consistency(volatility_pct: float) -> float:
    """
    Convert an annual volatility % to a 0–1 consistency score.
    Lower volatility → higher consistency.

    Scale: 0% vol → 1.0 consistency; 40% vol → 0.0 consistency.
    """
    return round(max(0.0, 1.0 - (volatility_pct / 40.0)), 3)


def score_fund(fund: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a market-aware score for a single fund.

    Parameters
    ----------
    fund : dict
        A fund dict (from recommendation_engine output).
        Expected keys: ``name``, ``category``, ``1y``, ``3y``, ``5y``,
        ``volatility``, ``sharpe``, ``allocation_weight``.
    signals : dict
        Output of ``market_signals.generate_signals()``.

    Returns
    -------
    dict
        Original fund dict extended with:
        ``ai_score``         – composite score (0–100 scale)
        ``market_fit_score`` – 0–1 signal-based fit
        ``consistency``      – 0–1 inverse volatility measure
        ``ai_reason``        – plain-English scoring rationale
    """
    scored = deepcopy(fund)

    ret_1y     = fund.get("1y", 0.0)
    ret_3y     = fund.get("3y", 0.0)
    vol_pct    = fund.get("volatility", 15.0)
    category   = fund.get("category", "")

    consistency       = _compute_consistency(vol_pct)
    market_fit        = _compute_market_fit_score(category, signals)

    # Raw score on a 0–100 scale (returns are already %)
    raw_score = (
        0.30 * ret_1y
        + 0.30 * ret_3y
        + 0.20 * consistency * 100    # scale to % space
        + 0.20 * market_fit  * 100    # scale to % space
    )

    ai_score = round(max(0.0, raw_score), 2)

    # ── Human-readable reason ─────────────────────────────────────────────────
    trend   = signals.get("market_trend", "bullish")
    vol_sig = signals.get("volatility", "medium")
    reason_parts = []

    reason_parts.append(
        f"Scored {ai_score:.1f}/100 based on 1Y/3Y returns ({ret_1y}% / {ret_3y}%), "
        f"consistency ({consistency:.0%}), and market-fit ({market_fit:.0%})."
    )

    # Market fit narrative
    if market_fit > 0.65:
        reason_parts.append(
            f"This category ({category}) is a strong fit for the current "
            f"{'bearish' if trend == 'bearish' else 'bullish'} market with "
            f"{'high' if vol_sig == 'high' else vol_sig} volatility."
        )
    elif market_fit < 0.50:
        reason_parts.append(
            f"This category ({category}) is a partial fit under current conditions — "
            "consider weighting other funds higher if risk is a concern."
        )

    scored["ai_score"]         = ai_score
    scored["market_fit_score"] = market_fit
    scored["consistency"]      = consistency
    scored["ai_reason"]        = " ".join(reason_parts)

    return scored


def rank_funds(
    funds: List[Dict[str, Any]],
    signals: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Score and rank all funds by their market-aware AI score.

    Parameters
    ----------
    funds : list
        List of fund dicts from recommendation_engine.
    signals : dict
        Output of ``market_signals.generate_signals()``.

    Returns
    -------
    list
        Same fund list, each extended with ``ai_score``, ``market_fit_score``,
        ``consistency``, and ``ai_reason``. Sorted descending by ``ai_score``.
    """
    if not funds:
        return []

    scored = [score_fund(f, signals) for f in funds]
    scored.sort(key=lambda x: x.get("ai_score", 0.0), reverse=True)
    return scored
