"""
Tests for backend/processors/output_formatter.py
"""
import pytest
from backend.processors.output_formatter import (
    get_confidence_band,
    get_disclaimer,
    format_risk_summary,
    format_macro_summary,
    format_monte_carlo_summary,
    build_insight_cards,
    build_projection_assumptions,
    build_scenario_projections,
)


# ── Mock data helpers ────────────────────────────────────────────────────────

def _risk_data(score: float = 6.0, category: str = "Moderate (ML Pred)"):
    return {"score": score, "category": category}

def _macro_context(score: float = 0.75):
    return {
        "macro_context_score": score,
        "inflation_rate": 0.06,
        "interest_rate": 0.065,
        "interest_rate_trend": "stable",
        "commodity_trend": "neutral",
        "adjusted_confidence": 0.72,
        "explanation": "Stable conditions.",
    }

def _portfolio_data(div_score: int = 7):
    return {
        "diversification_score": div_score,
        "risk_exposure": "Moderate (45% Equity)",
        "total_corpus": 500000.0,
        "insights": ["Keep saving!"],
    }


# ── get_confidence_band ──────────────────────────────────────────────────────

class TestGetConfidenceBand:
    def test_high_band(self):
        band = get_confidence_band(0.85)
        assert band["label"] == "High"
        assert band["colour"] == "green"

    def test_medium_band(self):
        band = get_confidence_band(0.65)
        assert band["label"] == "Medium"
        assert band["colour"] == "yellow"

    def test_low_band(self):
        band = get_confidence_band(0.40)
        assert band["label"] == "Low"
        assert band["colour"] == "red"

    def test_boundary_high(self):
        band = get_confidence_band(0.80)
        assert band["label"] == "High"

    def test_boundary_medium(self):
        band = get_confidence_band(0.50)
        assert band["label"] == "Medium"

    def test_clamps_above_one(self):
        band = get_confidence_band(1.5)
        assert band["label"] == "High"

    def test_clamps_below_zero(self):
        band = get_confidence_band(-0.5)
        assert band["label"] == "Low"

    def test_pct_format(self):
        band = get_confidence_band(0.87)
        assert band["pct"] == "87%"


# ── get_disclaimer ────────────────────────────────────────────────────────────

def test_disclaimer_is_non_empty():
    d = get_disclaimer()
    assert isinstance(d, str) and len(d) > 20


def test_build_projection_assumptions_contains_required_fields():
    assumptions = build_projection_assumptions(
        inflation_rate=0.065,
        inflation_source="RBI CPI Q1 2026",
        roi=0.12,
        roi_basis="Goal-horizon moderate scenario assumption",
        sip_topup_rate=0.10,
    )
    assert assumptions["inflation_rate"] == "6.5% — Source: RBI CPI Q1 2026"
    assert assumptions["expected_roi"] == "12.0% — Basis: Goal-horizon moderate scenario assumption"
    assert assumptions["base_return_scenarios"]["conservative"] == "8%"
    assert assumptions["sip_topup_rate"] == "10.0% annual step-up"
    assert "LTCG" in assumptions["tax_treatment"]


# ── format_risk_summary ──────────────────────────────────────────────────────

class TestFormatRiskSummary:
    def test_returns_all_keys(self):
        result = format_risk_summary(_risk_data())
        assert "simple" in result and "detailed" in result and "raw" in result

    def test_conservative_summary(self):
        result = format_risk_summary(_risk_data(3.0, "Conservative (ML Pred)"))
        assert "safety" in result["simple"].lower() or "safe" in result["simple"].lower()

    def test_aggressive_summary(self):
        result = format_risk_summary(_risk_data(8.5, "Aggressive (ML Pred)"))
        assert "aggressive" not in result["simple"].lower() or "growth" in result["simple"].lower()

    def test_detailed_contains_score(self):
        result = format_risk_summary(_risk_data(7.1, "Aggressive (ML Pred)"))
        assert "7.1" in result["detailed"]

    def test_raw_is_same_object(self):
        data = _risk_data()
        result = format_risk_summary(data)
        assert result["raw"] is data


# ── format_monte_carlo_summary ───────────────────────────────────────────────

class TestFormatMonteCarlo:
    def test_high_probability(self):
        result = format_monte_carlo_summary(85)
        assert "85" in result["simple"] or "85" in result["detailed"]
        assert "secure" in result["simple"].lower() or "great" in result["simple"].lower()

    def test_low_probability(self):
        result = format_monte_carlo_summary(30)
        assert "30" in result["simple"]

    def test_with_macro_context(self):
        result = format_monte_carlo_summary(75, _macro_context())
        assert "72%" in result["detailed"]  # adjusted_confidence = 0.72

    def test_raw_contains_probability(self):
        result = format_monte_carlo_summary(60)
        assert result["raw"]["probability"] == 60


# ── build_insight_cards ──────────────────────────────────────────────────────

class TestBuildInsightCards:
    def test_returns_three_cards(self):
        cards = build_insight_cards(_risk_data(), 75.0, _portfolio_data())
        assert len(cards) == 3

    def test_card_has_required_fields(self):
        cards = build_insight_cards(_risk_data(), 75.0, _portfolio_data())
        for card in cards:
            assert "title" in card
            assert "value" in card
            assert "colour" in card
            assert "recommendation" in card

    def test_high_probability_gives_green_goal_card(self):
        cards = build_insight_cards(_risk_data(), 90.0, _portfolio_data())
        goal_card = next(c for c in cards if c["title"] == "Goal Achievement")
        assert goal_card["colour"] == "green"

    def test_low_probability_gives_red_goal_card(self):
        cards = build_insight_cards(_risk_data(), 30.0, _portfolio_data())
        goal_card = next(c for c in cards if c["title"] == "Goal Achievement")
        assert goal_card["colour"] == "red"


# ── build_scenario_projections ───────────────────────────────────────────────

class TestBuildScenarioProjections:
    def test_returns_three_scenarios(self):
        result = build_scenario_projections(100000, 5000, 10)
        assert len(result) == 3

    def test_scenario_names(self):
        result = build_scenario_projections(100000, 5000, 10)
        names = [s["scenario"] for s in result]
        assert "Conservative" in names
        assert "Moderate" in names
        assert "Aggressive" in names

    def test_aggressive_greater_than_conservative(self):
        result = build_scenario_projections(100000, 5000, 10)
        by_name = {s["scenario"]: s["final_corpus"] for s in result}
        assert by_name["Aggressive"] > by_name["Moderate"] > by_name["Conservative"]

    def test_zero_corpus(self):
        result = build_scenario_projections(0, 5000, 5)
        for sc in result:
            assert sc["final_corpus"] > 0  # SIP alone should grow

    def test_zero_sip(self):
        result = build_scenario_projections(100000, 0, 10)
        for sc in result:
            assert sc["final_corpus"] >= 100000  # corpus should at least grow

    def test_inflation_adjusted_corpus_is_lower_than_nominal(self):
        result = build_scenario_projections(100000, 5000, 10, inflation_rate=0.06)
        for sc in result:
            assert sc["inflation_adjusted_corpus"] < sc["final_corpus"]

    def test_probability_mapping_is_applied(self):
        result = build_scenario_projections(
            100000,
            5000,
            10,
            success_probabilities={
                "conservative": 62.4,
                "moderate": 74.8,
                "aggressive": 83.1,
            },
        )
        by_name = {s["scenario"]: s for s in result}
        assert by_name["Conservative"]["probability"] == 62.4
        assert by_name["Moderate"]["probability"] == 74.8
        assert by_name["Aggressive"]["probability"] == 83.1
