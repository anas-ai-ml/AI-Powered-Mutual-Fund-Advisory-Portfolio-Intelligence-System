"""
Tests for backend/engines/intelligence/context_engine.py
"""
import pytest
from backend.engines.intelligence.context_engine import (
    get_macro_context,
    _compute_inflation_impact,
)


class TestComputeInflationImpact:
    def test_very_low_inflation(self):
        assert _compute_inflation_impact(0.02) == 0.0

    def test_at_rbi_target(self):
        impact = _compute_inflation_impact(0.06)
        assert impact == pytest.approx(0.3, abs=0.01)

    def test_high_inflation(self):
        impact = _compute_inflation_impact(0.10)
        assert impact == pytest.approx(0.7, abs=0.01)

    def test_extreme_inflation(self):
        assert _compute_inflation_impact(0.20) == 1.0


class TestGetMacroContext:
    def test_returns_all_required_keys(self):
        result = get_macro_context()
        required_keys = [
            "macro_context_score",
            "inflation_impact",
            "geopolitical_risk",
            "market_volatility",
            "interest_rate_trend",
            "commodity_trend",
            "interest_rate",
            "inflation_rate",
            "adjusted_confidence",
            "explanation",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_scores_are_in_valid_range(self):
        result = get_macro_context()
        assert 0.0 <= result["macro_context_score"] <= 1.0
        assert 0.0 <= result["adjusted_confidence"] <= 1.0
        assert 0.0 <= result["inflation_impact"] <= 1.0
        assert 0.0 <= result["geopolitical_risk"] <= 1.0
        assert 0.0 <= result["market_volatility"] <= 1.0

    def test_neutral_scenario(self):
        """Zero risk inputs → context score near 1.0."""
        result = get_macro_context(
            inflation_rate=0.02,
            geopolitical_risk=0.0,
            market_volatility=0.0,
            interest_rate_trend="stable",
            commodity_trend="neutral",
            base_confidence=1.0,
        )
        assert result["macro_context_score"] >= 0.90
        assert result["adjusted_confidence"] >= 0.90

    def test_high_risk_reduces_confidence(self):
        """High macro risk should reduce confidence from baseline."""
        low_risk = get_macro_context(
            inflation_rate=0.03, geopolitical_risk=0.0, market_volatility=0.0
        )
        high_risk = get_macro_context(
            inflation_rate=0.12, geopolitical_risk=0.8, market_volatility=0.8
        )
        assert high_risk["adjusted_confidence"] < low_risk["adjusted_confidence"]

    def test_custom_confidence_base(self):
        result = get_macro_context(base_confidence=0.90)
        # With default risks, adjusted should be less than base
        assert result["adjusted_confidence"] < 0.90

    def test_rising_rates_increase_risk(self):
        stable = get_macro_context(interest_rate_trend="stable")
        rising = get_macro_context(interest_rate_trend="rising")
        assert rising["geopolitical_risk"] >= stable["geopolitical_risk"]

    def test_explanation_is_non_empty_string(self):
        result = get_macro_context()
        assert isinstance(result["explanation"], str)
        assert len(result["explanation"]) > 10

    def test_fallback_on_invalid_input(self):
        """No exceptions raised even with edge-case inputs."""
        result = get_macro_context(
            inflation_rate=0.0,
            geopolitical_risk=0.0,
            market_volatility=0.0,
            base_confidence=0.0,
        )
        assert result["adjusted_confidence"] == 0.0
        assert result["macro_context_score"] == pytest.approx(1.0, abs=0.01)
