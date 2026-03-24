"""
Tests for ai_layer/signal_engine/market_signals.py
"""
import pytest
from ai_layer.signal_engine.market_signals import (
    classify_volatility,
    classify_trend,
    classify_global_sentiment,
    classify_usdinr_pressure,
    generate_signals,
)


class TestClassifyVolatility:
    def test_low(self):
        assert classify_volatility(10.0) == "low"

    def test_medium(self):
        assert classify_volatility(17.0) == "medium"

    def test_high(self):
        assert classify_volatility(25.0) == "high"

    def test_boundary_low_medium(self):
        assert classify_volatility(13.0) == "medium"  # exactly at boundary

    def test_boundary_medium_high(self):
        assert classify_volatility(20.0) == "medium"

    def test_above_high(self):
        assert classify_volatility(30.0) == "high"


class TestClassifyTrend:
    def test_bullish(self):
        assert classify_trend(22500.0, 21000.0) == "bullish"

    def test_bearish(self):
        assert classify_trend(20000.0, 22000.0) == "bearish"

    def test_equal(self):
        # Equal DMA → bearish (50 not > 200)
        assert classify_trend(22000.0, 22000.0) == "bearish"


class TestClassifyGlobalSentiment:
    def test_positive(self):
        assert classify_global_sentiment(1.0, 0.5) == "positive"

    def test_negative_sp500_down(self):
        assert classify_global_sentiment(-1.5, 0.0) == "negative"

    def test_negative_crude_surge(self):
        assert classify_global_sentiment(0.0, 2.0) == "negative"

    def test_neutral(self):
        assert classify_global_sentiment(0.2, 0.4) == "neutral"


class TestClassifyUsdinrPressure:
    def test_weakening(self):
        assert classify_usdinr_pressure(0.5) == "inr_weakening"

    def test_strengthening(self):
        assert classify_usdinr_pressure(-0.5) == "inr_strengthening"

    def test_stable(self):
        assert classify_usdinr_pressure(0.1) == "stable"


class TestGenerateSignals:
    def _mock_snapshot(self):
        return {
            "nifty":  {"price": 22500.0, "change_pct": 0.5, "dma_50": 22000.0, "dma_200": 21000.0},
            "vix":    {"price": 10.0, "change_pct": 0.0},
            "sp500":  {"price": 5200.0, "change_pct": 0.8},
            "crude":  {"price": 85.0, "change_pct": 0.3},
            "usdinr": {"price": 83.5, "change_pct": 0.1},
            "sensex": {"price": 74000.0, "change_pct": 0.4},
            "_meta":  {"is_fully_live": True, "live_count": 6, "total_count": 6},
        }

    def _mock_macro(self):
        return {
            "cpi_yoy_pct":   6.1,
            "repo_rate_pct": 6.5,
            "bond_yield_pct": 7.1,
            "inflation_trend": "stable",
            "rate_trend":      "stable",
            "source": "live",
        }

    def test_returns_all_required_keys(self):
        signals = generate_signals(self._mock_snapshot(), self._mock_macro())
        required = [
            "market_trend", "volatility", "inflation_trend",
            "interest_rate_trend", "global_sentiment",
            "usdinr_pressure", "golden_cross", "vix_level",
            "cpi_yoy_pct", "repo_rate_pct", "signal_source",
        ]
        for key in required:
            assert key in signals, f"Missing key: {key}"

    def test_bullish_golden_cross(self):
        signals = generate_signals(self._mock_snapshot(), self._mock_macro())
        assert signals["market_trend"] == "bullish"
        assert signals["golden_cross"] is True

    def test_low_vix(self):
        signals = generate_signals(self._mock_snapshot(), self._mock_macro())
        assert signals["volatility"] == "low"

    def test_cpi_passed_through(self):
        signals = generate_signals(self._mock_snapshot(), self._mock_macro())
        assert signals["cpi_yoy_pct"] == pytest.approx(6.1)

    def test_empty_snapshot_doesnt_crash(self):
        signals = generate_signals({}, {})
        assert "market_trend" in signals
