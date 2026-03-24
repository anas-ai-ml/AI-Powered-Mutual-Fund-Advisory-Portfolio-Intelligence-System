"""
ai_layer/explanation_engine/narrative_builder.py
────────────────────────────────────────────────
Converts AI layer decisions into concise, human-readable narratives
suitable for display to clients and advisors.

Three narrative types:
  1. Market Summary      — What is happening in the market right now?
  2. Allocation Rationale — Why was the portfolio adjusted this way?
  3. Risk Narrative       — What does this mean for the investor's risk?

All text is plain English, jargon-free, and advisor-ready.
"""

from datetime import datetime
from typing import Any, Dict, List


# ── Utility: format a delta as "+5%" or "-3%" ─────────────────────────────────
def _fmt_delta(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


# ── 1. Market Summary ─────────────────────────────────────────────────────────

def build_market_summary(
    signals: Dict[str, Any],
    market_snapshot: Dict[str, Any],
    macro_indicators: Dict[str, Any],
) -> str:
    """
    Generate a 2–3 sentence plain-English market summary.

    Parameters
    ----------
    signals : dict
        Output of ``market_signals.generate_signals()``.
    market_snapshot : dict
        Output of ``market_data.get_market_snapshot()``.
    macro_indicators : dict
        Output of ``macro_data.get_macro_indicators()``.

    Returns
    -------
    str  Human-readable market summary paragraph.
    """
    trend    = signals.get("market_trend", "bullish")
    vol      = signals.get("volatility", "medium")
    sent     = signals.get("global_sentiment", "neutral")
    nifty    = signals.get("nifty_price", 0.0)
    nifty_ch = signals.get("nifty_change_pct", 0.0)
    vix      = signals.get("vix_level", 15.0)
    cpi      = signals.get("cpi_yoy_pct", 6.0)
    repo     = signals.get("repo_rate_pct", 6.5)
    crude    = signals.get("crude_price", 85.0)
    usdinr   = signals.get("usdinr_price", 83.5)

    # Trend sentence
    if trend == "bullish":
        trend_txt = (
            f"Indian equity markets are in a **bullish phase** — "
            f"Nifty 50 is at {nifty:,.0f} ({'+' if nifty_ch >= 0 else ''}{nifty_ch:.2f}% today), "
            "with its short-term average above its long-term average (a positive signal)."
        )
    else:
        trend_txt = (
            f"Indian equity markets are in a **bearish phase** — "
            f"Nifty 50 is at {nifty:,.0f} ({'+' if nifty_ch >= 0 else ''}{nifty_ch:.2f}% today), "
            "with its short-term average below its long-term average (a caution signal)."
        )

    # Volatility sentence
    vol_map = {
        "low":    f"Market volatility is **low** (VIX {vix:.1f}), indicating calm conditions.",
        "medium": f"Market volatility is **moderate** (VIX {vix:.1f}), suggesting some uncertainty.",
        "high":   f"Market volatility is **elevated** (VIX {vix:.1f}), indicating heightened risk and uncertainty.",
    }
    vol_txt = vol_map.get(vol, f"VIX is at {vix:.1f}.")

    # Macro sentence
    macro_txt = (
        f"India's inflation is running at **{cpi:.1f}%** annually "
        f"and the RBI repo rate is **{repo:.2f}%**. "
        f"Crude oil is at **${crude:.1f}/barrel** and USD-INR is at **{usdinr:.2f}**."
    )

    # Global sentiment
    sent_map = {
        "positive": "Global markets are broadly **supportive**, with S&P 500 up and commodity prices stable.",
        "neutral":  "Global markets are in a **wait-and-watch** mode with mixed signals.",
        "negative": "Global sentiment is **cautious** — S&P 500 weakness or surging crude oil signal headwinds.",
    }
    sent_txt = sent_map.get(sent, "")

    return " ".join(filter(None, [trend_txt, vol_txt, macro_txt, sent_txt]))


# ── 2. Allocation Rationale ───────────────────────────────────────────────────

def build_allocation_rationale(
    adaptive_result: Dict[str, Any],
    signals: Dict[str, Any],
) -> str:
    """
    Explain why the portfolio allocation was adjusted from its MPT baseline.

    Parameters
    ----------
    adaptive_result : dict
        Output of ``adaptive_allocation.apply_adaptive_allocation()``.
    signals : dict
        Output of ``market_signals.generate_signals()``.

    Returns
    -------
    str  Human-readable allocation rationale.
    """
    eq_delta  = adaptive_result.get("equity_delta", 0.0)
    dbt_delta = adaptive_result.get("debt_delta",   0.0)
    gld_delta = adaptive_result.get("gold_delta",   0.0)
    reasons   = adaptive_result.get("adjustment_reasons", [])

    if not reasons or (eq_delta == 0 and dbt_delta == 0 and gld_delta == 0):
        return (
            "The current market environment is broadly stable. "
            "Your allocation follows the optimal mix calculated by the portfolio model, "
            "with no significant macro-driven adjustments required at this time."
        )

    # Opening line
    parts = [
        "Based on live market signals, the AI engine has adjusted your target allocation:"
    ]

    if eq_delta != 0:
        direction = "increased" if eq_delta > 0 else "reduced"
        parts.append(
            f"**Equity** has been {direction} by **{_fmt_delta(abs(eq_delta))}**."
        )
    if dbt_delta != 0:
        direction = "increased" if dbt_delta > 0 else "reduced"
        parts.append(
            f"**Debt** has been {direction} by **{_fmt_delta(abs(dbt_delta))}**."
        )
    if gld_delta != 0:
        direction = "increased" if gld_delta > 0 else "reduced"
        parts.append(
            f"**Gold** has been {direction} by **{_fmt_delta(abs(gld_delta))}**."
        )

    parts.append("\n**Reason(s):**")
    for r in reasons:
        parts.append(f"• {r}")

    return " ".join(parts[:3]) + "\n\n" + "\n".join(parts[3:])


# ── 3. Risk Narrative ─────────────────────────────────────────────────────────

def build_risk_narrative(
    signals: Dict[str, Any],
    risk_category: str,
) -> str:
    """
    Explain what current market conditions mean for this investor's risk level.

    Parameters
    ----------
    signals : dict
        Output of ``market_signals.generate_signals()``.
    risk_category : str
        The investor's risk category string (e.g. "Moderate (ML Pred)").

    Returns
    -------
    str  Human-readable risk narrative.
    """
    cat = risk_category.split("(")[0].strip().lower()
    vol = signals.get("volatility", "medium")
    trend = signals.get("market_trend", "bullish")
    inf   = signals.get("inflation_trend", "stable")

    risk_compat: Dict[str, Dict[str, str]] = {
        "conservative": {
            "high":   "High volatility is a concern for your Conservative profile. "
                      "The current allocation already leans towards capital protection — "
                      "avoid reducing your debt holdings during this period.",
            "medium": "Moderate volatility is manageable for a Conservative investor. "
                      "Stay the course with your plan and avoid reactive changes.",
            "low":    "Low volatility is a comfortable environment for Conservative investors. "
                      "Consider a slight equity tilt to improve long-term inflation-adjusted returns.",
        },
        "moderate": {
            "high":   "High volatility warrants a brief defensive posture even for Moderate investors. "
                      "The adaptive allocation has already trimmed equity — review in 2–4 weeks.",
            "medium": "Moderate volatility is your ideal operating environment. "
                      "Your balanced allocation is well-positioned for the current market.",
            "low":    "Low volatility is an opportunity for Moderate investors to hold equity "
                      "with confidence and benefit from compounding.",
        },
        "aggressive": {
            "high":   "Even Aggressive investors should note high VIX conditions. "
                      "The equity allocation has been trimmed slightly as a risk control measure — "
                      "this is temporary and can be unwound when volatility subsides.",
            "medium": "Moderate volatility is within the expected range for an Aggressive portfolio. "
                      "Quality small and mid-cap funds should continue performing well over the medium term.",
            "low":    "Low volatility and a bullish market are ideal conditions for your Aggressive profile. "
                      "The current allocation maximises your exposure to high-growth opportunities.",
        },
    }

    base = risk_compat.get(cat, risk_compat["moderate"]).get(vol, "")

    # Add inflation note
    inf_note = ""
    if inf == "rising":
        inf_note = (
            " Rising inflation means the real value of cash and fixed deposits erodes faster — "
            "equities and gold remain your best long-term hedge."
        )
    elif inf == "falling":
        inf_note = (
            " Falling inflation supports bond prices and debt returns — "
            "a slight tilt towards debt funds could be beneficial."
        )

    trend_note = ""
    if trend == "bearish" and cat == "aggressive":
        trend_note = (
            " The bearish market trend is a short-term caution signal — "
            "avoid adding fresh lump-sum equity positions until the 50DMA crosses back above the 200DMA."
        )

    return base + inf_note + trend_note


# ── 4. Full Intelligence Report ───────────────────────────────────────────────

def build_full_narrative(
    signals: Dict[str, Any],
    market_snapshot: Dict[str, Any],
    macro_indicators: Dict[str, Any],
    adaptive_result: Dict[str, Any],
    risk_category: str,
) -> Dict[str, str]:
    """
    Build the complete set of AI-generated narratives.

    Returns a dict with keys:
      ``market_summary``, ``allocation_rationale``, ``risk_narrative``,
      ``generated_at``.
    """
    return {
        "market_summary":       build_market_summary(signals, market_snapshot, macro_indicators),
        "allocation_rationale": build_allocation_rationale(adaptive_result, signals),
        "risk_narrative":       build_risk_narrative(signals, risk_category),
        "generated_at":         datetime.now().isoformat(timespec="seconds"),
    }
