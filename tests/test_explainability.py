"""
Tests for backend/processors/explainability.py
"""
import pytest
from backend.processors.explainability import (
    explain_risk_profile,
    explain_fund_recommendation,
    explain_all_funds,
    explain_portfolio_health,
)


# ── Mock data helpers ────────────────────────────────────────────────────────

def _risk_data(score: float = 6.0, category: str = "Moderate (ML Pred)"):
    return {
        "score": score,
        "category": category,
        "explanation": {"features": {"age_input": 35, "dependents": 1, "savings_ratio": 0.3}},
    }

def _client_data(**overrides):
    base = {
        "age": 35,
        "dependents": 1,
        "monthly_income": 100000,
        "monthly_savings": 30000,
        "behavior": "Moderate",
    }
    base.update(overrides)
    return base

def _fund(
    name: str = "SBI Blue Chip Fund",
    category: str = "Large Cap",
    risk: str = "Moderate (ML Pred)",
    weight: float = 30.0,
    sharpe: float = 1.1,
    volatility: float = 12.0,
    ret_1y: float = 14.0,
    ret_3y: float = 12.0,
    ret_5y: float = 11.5,
):
    return {
        "name": name,
        "category": category,
        "risk": risk,
        "allocation_weight": weight,
        "sharpe": sharpe,
        "volatility": volatility,
        "1y": ret_1y,
        "3y": ret_3y,
        "5y": ret_5y,
    }

def _portfolio_data(div_score: int = 7):
    return {
        "diversification_score": div_score,
        "risk_exposure": "Moderate (45% Equity)",
        "total_corpus": 500000.0,
        "insights": ["Some insight here."],
    }


# ── explain_risk_profile ─────────────────────────────────────────────────────

class TestExplainRiskProfile:
    def test_returns_required_keys(self):
        result = explain_risk_profile(_risk_data(), _client_data())
        assert "summary" in result
        assert "key_factors" in result
        assert "recommendation" in result

    def test_summary_contains_category(self):
        result = explain_risk_profile(
            _risk_data(6.0, "Moderate (ML Pred)"), _client_data()
        )
        assert "Moderate" in result["summary"]

    def test_key_factors_is_list_of_strings(self):
        result = explain_risk_profile(_risk_data(), _client_data())
        assert isinstance(result["key_factors"], list)
        for factor in result["key_factors"]:
            assert isinstance(factor, str)

    def test_young_user_age_factor(self):
        result = explain_risk_profile(_risk_data(), _client_data(age=25))
        joined = " ".join(result["key_factors"])
        assert "25" in joined

    def test_high_dependents_mentioned(self):
        result = explain_risk_profile(_risk_data(), _client_data(dependents=4))
        joined = " ".join(result["key_factors"])
        assert "4" in joined

    def test_zero_income_doesnt_crash(self):
        result = explain_risk_profile(_risk_data(), _client_data(monthly_income=0))
        assert isinstance(result["summary"], str)

    def test_conservative_recommendation(self):
        result = explain_risk_profile(
            _risk_data(3.0, "Conservative (ML Pred)"), _client_data()
        )
        assert "debt" in result["recommendation"].lower() or "protect" in result["recommendation"].lower()

    def test_aggressive_recommendation(self):
        result = explain_risk_profile(
            _risk_data(8.5, "Aggressive (ML Pred)"), _client_data()
        )
        assert "equity" in result["recommendation"].lower() or "growth" in result["recommendation"].lower()


# ── explain_fund_recommendation ──────────────────────────────────────────────

class TestExplainFundRecommendation:
    def test_returns_non_empty_string(self):
        reason = explain_fund_recommendation(_fund())
        assert isinstance(reason, str) and len(reason) > 20

    def test_fund_name_in_reason(self):
        reason = explain_fund_recommendation(_fund(name="HDFC Flexi Cap Fund"))
        assert "HDFC Flexi Cap Fund" in reason

    def test_high_return_mentioned(self):
        reason = explain_fund_recommendation(_fund(ret_1y=20.0))
        assert "20" in reason

    def test_low_return_mentioned(self):
        reason = explain_fund_recommendation(_fund(ret_1y=4.0))
        assert "4" in reason

    def test_gold_category(self):
        reason = explain_fund_recommendation(_fund(category="Gold"))
        assert "gold" in reason.lower() or "inflation" in reason.lower()

    def test_missing_keys_dont_crash(self):
        reason = explain_fund_recommendation({})
        assert isinstance(reason, str)


# ── explain_all_funds ─────────────────────────────────────────────────────────

class TestExplainAllFunds:
    def test_length_matches_input(self):
        funds = [_fund("Fund A"), _fund("Fund B"), _fund("Fund C")]
        result = explain_all_funds(funds)
        assert len(result) == 3

    def test_each_item_has_name_and_reason(self):
        funds = [_fund("Fund X")]
        result = explain_all_funds(funds)
        assert result[0]["name"] == "Fund X"
        assert isinstance(result[0]["reason"], str) and len(result[0]["reason"]) > 10

    def test_empty_list(self):
        result = explain_all_funds([])
        assert result == []


# ── explain_portfolio_health ──────────────────────────────────────────────────

class TestExplainPortfolioHealth:
    def test_returns_required_keys(self):
        result = explain_portfolio_health(_portfolio_data())
        assert "headline" in result
        assert "narrative" in result
        assert "verdict" in result

    def test_strong_verdict_for_high_score(self):
        result = explain_portfolio_health(_portfolio_data(div_score=9))
        assert result["verdict"] == "strong"

    def test_moderate_verdict_for_mid_score(self):
        result = explain_portfolio_health(_portfolio_data(div_score=6))
        assert result["verdict"] == "moderate"

    def test_needs_attention_for_low_score(self):
        result = explain_portfolio_health(_portfolio_data(div_score=3))
        assert result["verdict"] == "needs_attention"

    def test_corpus_in_narrative(self):
        result = explain_portfolio_health(_portfolio_data(div_score=7))
        assert "500,000" in result["narrative"] or "5,00,000" in result["narrative"] or "500000" in result["narrative"].replace(",", "")

    def test_zero_corpus(self):
        data = {"diversification_score": 0, "risk_exposure": "N/A", "total_corpus": 0.0, "insights": []}
        result = explain_portfolio_health(data)
        assert isinstance(result["headline"], str)
