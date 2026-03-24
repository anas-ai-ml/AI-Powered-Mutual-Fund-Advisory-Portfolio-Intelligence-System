"""
Tests for ai_layer/decision_engine/ and ai_layer/scoring_engine/
"""
import pytest
from ai_layer.decision_engine.allocation_rules import (
    rule_high_volatility,
    rule_bearish_market,
    rule_rising_inflation,
    rule_rising_rates,
    rule_negative_global_sentiment,
    evaluate_all_rules,
)
from ai_layer.decision_engine.adaptive_allocation import apply_adaptive_allocation
from ai_layer.scoring_engine.fund_scoring import (
    _compute_consistency,
    _compute_market_fit_score,
    score_fund,
    rank_funds,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _base_alloc():
    return {
        "Equity - Large Cap": 40.0,
        "Equity - Mid Cap":   15.0,
        "Debt":               35.0,
        "Gold":               10.0,
    }

def _neutral_signals():
    return {
        "market_trend":        "bullish",
        "volatility":          "medium",
        "inflation_trend":     "stable",
        "interest_rate_trend": "stable",
        "global_sentiment":    "neutral",
        "usdinr_pressure":     "stable",
    }

def _fund(**overrides):
    base = {
        "name": "Test Fund", "category": "Large Cap",
        "risk": "Moderate", "allocation_weight": 30.0,
        "sharpe": 1.0, "volatility": 12.0,
        "1y": 14.0, "3y": 12.0, "5y": 11.0,
    }
    base.update(overrides)
    return base


# ── Allocation Rules ──────────────────────────────────────────────────────────

class TestAllocationRules:
    def test_high_volatility_reduces_equity(self):
        eq, dbt, gld, reason = rule_high_volatility("high")
        assert eq < 0 and dbt > 0
        assert reason != ""

    def test_no_change_for_low_volatility(self):
        eq, dbt, gld, reason = rule_high_volatility("low")
        assert eq == 0 and dbt == 0 and reason == ""

    def test_bearish_reduces_equity(self):
        eq, dbt, gld, reason = rule_bearish_market("bearish")
        assert eq < 0 and dbt > 0

    def test_bullish_no_change(self):
        eq, dbt, gld, reason = rule_bearish_market("bullish")
        assert eq == 0

    def test_rising_inflation_boosts_equity_gold(self):
        eq, dbt, gld, reason = rule_rising_inflation("rising")
        assert eq > 0 and gld > 0 and dbt < 0

    def test_rising_rates_hurts_debt(self):
        eq, dbt, gld, reason = rule_rising_rates("rising")
        assert dbt < 0

    def test_negative_global_adds_gold(self):
        eq, dbt, gld, reason = rule_negative_global_sentiment("negative")
        assert gld > 0 and eq < 0


class TestEvaluateAllRules:
    def test_neutral_signals_produce_minimal_delta(self):
        eq, dbt, gld, reasons = evaluate_all_rules(_neutral_signals())
        # Medium vol + bullish adds mild equity tilt
        assert isinstance(reasons, list)

    def test_bearish_high_vol_reduces_equity(self):
        signals = _neutral_signals()
        signals["market_trend"] = "bearish"
        signals["volatility"]   = "high"
        eq, dbt, gld, reasons = evaluate_all_rules(signals)
        assert eq < 0
        assert dbt > 0
        assert len(reasons) >= 2

    def test_equity_delta_is_capped(self):
        # Even with all bearish signals, delta shouldn't exceed ±20
        signals = {
            "market_trend":        "bearish",
            "volatility":          "high",
            "inflation_trend":     "rising",
            "interest_rate_trend": "rising",
            "global_sentiment":    "negative",
            "usdinr_pressure":     "inr_weakening",
        }
        eq, dbt, gld, _ = evaluate_all_rules(signals)
        assert -20 <= eq <= 20
        assert -20 <= dbt <= 20


# ── Adaptive Allocation ───────────────────────────────────────────────────────

class TestAdaptiveAllocation:
    def test_returns_required_keys(self):
        result = apply_adaptive_allocation(_base_alloc(), _neutral_signals())
        for key in ("adaptive_allocation", "equity_delta", "debt_delta", "gold_delta", "adjustment_reasons"):
            assert key in result

    def test_adaptive_sums_to_100(self):
        result = apply_adaptive_allocation(_base_alloc(), _neutral_signals())
        total = sum(result["adaptive_allocation"].values())
        assert pytest.approx(total, abs=0.5) == 100.0

    def test_bearish_high_vol_shifts_weight_to_debt(self):
        signals = _neutral_signals()
        signals["market_trend"] = "bearish"
        signals["volatility"]   = "high"
        result = apply_adaptive_allocation(_base_alloc(), signals)
        base_equity = _base_alloc()["Equity - Large Cap"] + _base_alloc()["Equity - Mid Cap"]
        new_equity  = sum(v for k, v in result["adaptive_allocation"].items() if "Equity" in k)
        assert new_equity < base_equity

    def test_no_negative_weights(self):
        result = apply_adaptive_allocation(_base_alloc(), _neutral_signals())
        for w in result["adaptive_allocation"].values():
            assert w >= 0

    def test_empty_allocation_doesnt_crash(self):
        result = apply_adaptive_allocation({}, _neutral_signals())
        assert isinstance(result["adaptive_allocation"], dict)


# ── Fund Scoring ──────────────────────────────────────────────────────────────

class TestFundScoring:
    def test_consistency_high_for_low_vol(self):
        assert _compute_consistency(0.0) == 1.0

    def test_consistency_low_for_high_vol(self):
        assert _compute_consistency(40.0) == 0.0

    def test_large_cap_fit_in_bearish(self):
        signals = _neutral_signals()
        signals["market_trend"] = "bearish"
        signals["volatility"]   = "high"
        fit = _compute_market_fit_score("Large Cap", signals)
        assert fit > 0.65

    def test_mid_cap_fit_in_bullish(self):
        signals = _neutral_signals()
        signals["market_trend"] = "bullish"
        signals["volatility"]   = "low"
        fit = _compute_market_fit_score("Mid Cap", signals)
        assert fit > 0.60

    def test_score_fund_returns_ai_score(self):
        result = score_fund(_fund(), _neutral_signals())
        assert "ai_score" in result
        assert result["ai_score"] >= 0

    def test_score_fund_returns_ai_reason(self):
        result = score_fund(_fund(), _neutral_signals())
        assert isinstance(result["ai_reason"], str) and len(result["ai_reason"]) > 10

    def test_rank_funds_sorted_desc(self):
        funds = [
            _fund(name="Fund A", **{"1y": 5.0,  "3y": 6.0}),
            _fund(name="Fund B", **{"1y": 18.0, "3y": 15.0}),
            _fund(name="Fund C", **{"1y": 10.0, "3y": 10.0}),
        ]
        ranked = rank_funds(funds, _neutral_signals())
        scores = [r["ai_score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_funds_empty(self):
        assert rank_funds([], _neutral_signals()) == []
