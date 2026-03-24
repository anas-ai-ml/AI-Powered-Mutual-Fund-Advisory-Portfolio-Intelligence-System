"""
ai_layer/decision_engine/allocation_rules.py
─────────────────────────────────────────────
Defines the rule table that maps market signals to portfolio allocation
adjustments. Each rule is a pure function — no I/O, no side effects.

Rules return a tuple:
    (equity_delta, debt_delta, gold_delta, reason_string)
where deltas are in percentage points (e.g. -10 means reduce equity by 10pp).
"""

from typing import List, Tuple

# Type alias for a single rule output
RuleResult = Tuple[float, float, float, str]

# Zero-delta sentinel
_NO_CHANGE: RuleResult = (0.0, 0.0, 0.0, "")


def rule_high_volatility(volatility: str) -> RuleResult:
    """
    High VIX → reduce equity, increase debt (capital preservation).
    """
    if volatility == "high":
        return (
            -10.0, +10.0, 0.0,
            "High market volatility (VIX elevated): equity reduced by 10% to preserve capital."
        )
    return _NO_CHANGE


def rule_bearish_market(market_trend: str) -> RuleResult:
    """
    Death-Cross → reduce equity slightly, increase debt.
    """
    if market_trend == "bearish":
        return (
            -5.0, +5.0, 0.0,
            "Market in bearish phase (50DMA < 200DMA): equity trimmed by 5%, favouring debt."
        )
    return _NO_CHANGE


def rule_rising_inflation(inflation_trend: str) -> RuleResult:
    """
    Rising inflation → equities are an inflation hedge, add slightly.
    Gold also benefits; offset from debt (real yields compressed).
    """
    if inflation_trend == "rising":
        return (
            +3.0, -5.0, +2.0,
            "Rising inflation: equity (+3%) and gold (+2%) increased as inflation hedges; "
            "debt reduced by 5% (compressed real yields)."
        )
    return _NO_CHANGE


def rule_rising_rates(interest_rate_trend: str) -> RuleResult:
    """
    Rising interest rates hurt bonds (prices fall); reduce debt.
    Floating-rate and equity can absorb this better.
    """
    if interest_rate_trend == "rising":
        return (
            +2.0, -5.0, +3.0,
            "Rising interest rates: debt reduced by 5% (bond price risk); "
            "gold +3% as safe haven; equity +2%."
        )
    return _NO_CHANGE


def rule_falling_rates(interest_rate_trend: str) -> RuleResult:
    """
    Falling rates → bonds rally, increase debt allocation.
    """
    if interest_rate_trend == "falling":
        return (
            0.0, +5.0, 0.0,
            "Falling interest rates: debt increased by 5% as bond prices rally."
        )
    return _NO_CHANGE


def rule_negative_global_sentiment(global_sentiment: str) -> RuleResult:
    """
    Negative global sentiment (weak S&P, surging crude) → add gold as safe haven.
    """
    if global_sentiment == "negative":
        return (
            -3.0, 0.0, +3.0,
            "Negative global sentiment (weak S&P 500 / surging crude): "
            "gold +3% as safe haven, equity -3%."
        )
    return _NO_CHANGE


def rule_inr_weakening(usdinr_pressure: str) -> RuleResult:
    """
    Weakening INR is inflationary and signals foreign outflows.
    Slightly defensive posture.
    """
    if usdinr_pressure == "inr_weakening":
        return (
            -2.0, +2.0, 0.0,
            "INR weakening against USD: slight defensive shift — equity -2%, debt +2%."
        )
    return _NO_CHANGE


def rule_medium_volatility(volatility: str, market_trend: str) -> RuleResult:
    """
    Medium volatility + bullish trend → modest equity tilt upward.
    """
    if volatility == "medium" and market_trend == "bullish":
        return (
            +3.0, -3.0, 0.0,
            "Medium volatility with bullish trend: mild equity tilt (+3%) in favour of growth."
        )
    return _NO_CHANGE


# ── Aggregator ────────────────────────────────────────────────────────────────

def evaluate_all_rules(signals: dict) -> Tuple[float, float, float, List[str]]:
    """
    Evaluate all rules against the current signals dict.

    Parameters
    ----------
    signals : dict
        Output of ``market_signals.generate_signals()``.

    Returns
    -------
    tuple
        (total_equity_delta, total_debt_delta, total_gold_delta, reasons_list)
    """
    rule_outputs: List[RuleResult] = [
        rule_high_volatility(signals.get("volatility", "medium")),
        rule_bearish_market(signals.get("market_trend", "bullish")),
        rule_rising_inflation(signals.get("inflation_trend", "stable")),
        rule_rising_rates(signals.get("interest_rate_trend", "stable")),
        rule_falling_rates(signals.get("interest_rate_trend", "stable")),
        rule_negative_global_sentiment(signals.get("global_sentiment", "neutral")),
        rule_inr_weakening(signals.get("usdinr_pressure", "stable")),
        rule_medium_volatility(
            signals.get("volatility", "medium"),
            signals.get("market_trend", "bullish"),
        ),
    ]

    total_equity = 0.0
    total_debt   = 0.0
    total_gold   = 0.0
    reasons: List[str] = []

    for eq_d, dbt_d, gld_d, reason in rule_outputs:
        total_equity += eq_d
        total_debt   += dbt_d
        total_gold   += gld_d
        if reason:
            reasons.append(reason)

    # Cap total deltas to prevent extreme swings (±20pp on equity)
    total_equity = max(-20.0, min(+20.0, total_equity))
    total_debt   = max(-20.0, min(+20.0, total_debt))
    total_gold   = max(-10.0, min(+10.0, total_gold))

    return total_equity, total_debt, total_gold, reasons
