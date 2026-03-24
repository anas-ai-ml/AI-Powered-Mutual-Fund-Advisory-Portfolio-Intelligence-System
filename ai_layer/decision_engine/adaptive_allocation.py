"""
ai_layer/decision_engine/adaptive_allocation.py
────────────────────────────────────────────────
Applies rule-based deltas to the base MPT allocation from allocation_engine
and produces a market-aware adaptive portfolio.

Key design:
  - Takes the existing allocation dict as input (no re-computation).
  - Applies equity / debt / gold deltas from the rule engine.
  - Distributes residual adjustments proportionally across sub-categories.
  - Guarantees total == 100% after normalisation.
  - Returns the original allocation unchanged if signals are unavailable.
"""

import logging
from typing import Any, Dict, List, Tuple

from ai_layer.decision_engine.allocation_rules import evaluate_all_rules

logger = logging.getLogger(__name__)


def _classify_asset(key: str) -> str:
    """Map an allocation key to a broad asset class for rule application."""
    k = key.lower()
    if "debt" in k:
        return "debt"
    if "gold" in k:
        return "gold"
    return "equity"  # All equity sub-types


def apply_adaptive_allocation(
    base_allocation: Dict[str, float],
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce a market-aware allocation by applying signal-driven rule deltas
    on top of the existing MPT allocation.

    Parameters
    ----------
    base_allocation : dict
        Key → weight% from ``allocation_engine.get_asset_allocation()``.
        Example: {"Equity - Large Cap": 45.0, "Debt": 30.0, "Gold": 10.0, ...}
    signals : dict
        Output of ``market_signals.generate_signals()``.

    Returns
    -------
    dict
        ``base_allocation``       – original MPT allocation (unchanged)
        ``adaptive_allocation``   – market-adjusted allocation (sums to 100)
        ``equity_delta``          – total equity delta applied (pp)
        ``debt_delta``            – total debt delta applied (pp)
        ``gold_delta``            – total gold delta applied (pp)
        ``adjustment_reasons``    – list of plain-English reason strings
        ``total_check``           – sum of adaptive_allocation values (≈100)
    """
    try:
        eq_delta, dbt_delta, gld_delta, reasons = evaluate_all_rules(signals)

        # ── Group keys by asset class ─────────────────────────────────────────
        equity_keys = [k for k in base_allocation if _classify_asset(k) == "equity"]
        debt_keys   = [k for k in base_allocation if _classify_asset(k) == "debt"]
        gold_keys   = [k for k in base_allocation if _classify_asset(k) == "gold"]

        # ── Distribute deltas proportionally within each class ────────────────
        def _distribute(keys: List[str], delta: float) -> Dict[str, float]:
            total_weight = sum(base_allocation.get(k, 0.0) for k in keys)
            result: Dict[str, float] = {}
            for k in keys:
                w = base_allocation.get(k, 0.0)
                proportion = (w / total_weight) if total_weight > 0 else (1.0 / len(keys) if keys else 0.0)
                result[k] = w + delta * proportion
            return result

        adjusted: Dict[str, float] = {}

        if equity_keys:
            adjusted.update(_distribute(equity_keys, eq_delta))
        if debt_keys:
            adjusted.update(_distribute(debt_keys, dbt_delta))
        if gold_keys:
            adjusted.update(_distribute(gold_keys, gld_delta))

        # ── Keys not in any category pass through unchanged ───────────────────
        for k in base_allocation:
            if k not in adjusted:
                adjusted[k] = base_allocation[k]

        # ── Floor at 0 (no negative weights) ─────────────────────────────────
        adjusted = {k: max(0.0, v) for k, v in adjusted.items()}

        # ── Normalise to 100% ─────────────────────────────────────────────────
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: round((v / total) * 100.0, 2) for k, v in adjusted.items()}

        # Final sum check (may differ by tiny rounding error)
        total_check = round(sum(adjusted.values()), 2)

        if not reasons:
            reasons = ["No significant macro signals detected. Allocation unchanged from MPT optimum."]

        return {
            "base_allocation":     base_allocation,
            "adaptive_allocation": adjusted,
            "equity_delta":        round(eq_delta, 1),
            "debt_delta":          round(dbt_delta, 1),
            "gold_delta":          round(gld_delta, 1),
            "adjustment_reasons":  reasons,
            "total_check":         total_check,
        }

    except Exception as exc:
        logger.error("adaptive_allocation: Error applying rules — %s. Returning base.", exc)
        return {
            "base_allocation":     base_allocation,
            "adaptive_allocation": base_allocation,
            "equity_delta":        0.0,
            "debt_delta":          0.0,
            "gold_delta":          0.0,
            "adjustment_reasons":  ["Signal data unavailable. Using baseline MPT allocation."],
            "total_check":         round(sum(base_allocation.values()), 2),
        }
