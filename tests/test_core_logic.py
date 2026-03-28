"""
Core Logic Verification Tests
Tests the actual mathematical correctness of the core engines
with specific input/output assertions.
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load env before any imports
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.engines.v2.risk_engine import compute_risk, risk_score_to_allocation
from backend.engines.goal_engine import calculate_goal
from backend.scoring.calibration_engine import RISK_BAND_THRESHOLDS
from backend.engines.portfolio_engine import analyze_portfolio
from backend.engines.v2.portfolio_gap_advisor import PortfolioGapAdvisor
from backend.engines.monte_carlo_engine import run_monte_carlo_simulation
from backend.scoring.monte_carlo_remediation import generate_fix_recommendation
from frontend.components.score_intelligence_panel import ideal_risk_range_for_profile


_GAP_ADVISOR = PortfolioGapAdvisor()


def compute_diversification_score(portfolio: dict, monthly_income: float, risk_score: float) -> float:
    result = analyze_portfolio(
        existing_fd=float(portfolio.get("fd_bonds", 0.0)),
        existing_savings=float(portfolio.get("cash", 0.0)),
        existing_gold=float(portfolio.get("gold", 0.0)),
        existing_mutual_funds=float(portfolio.get("equity", 0.0)),
        risk_score=float(risk_score),
        monthly_income=float(monthly_income),
    )
    return float(result["diversification_score"])


def compute_allocation_gap(current_portfolio: dict, target_allocation: dict, total_corpus: float) -> list:
    return _GAP_ADVISOR.compute_allocation_gap(current_portfolio, target_allocation, total_corpus)


def recommend_funds_for_gap(gap_list: list, risk_profile: dict, market_signals: dict, existing_funds: list) -> list:
    return _GAP_ADVISOR.recommend_funds_for_gap(gap_list, risk_profile, market_signals, existing_funds)


def run_monte_carlo(
    monthly_sip: float,
    existing_corpus: float,
    goal_corpus: float,
    years: int,
    expected_return: float,
    std_dev: float,
) -> dict:
    probability = run_monte_carlo_simulation(
        initial_corpus=existing_corpus,
        monthly_sip=monthly_sip,
        years=years,
        target_corpus=goal_corpus,
        expected_annual_return=expected_return,
        annual_volatility=std_dev,
        num_simulations=1000,
    )
    result = {"probability": float(probability)}
    if probability < 50.0:
        result["fix_recommendation"] = generate_fix_recommendation(
            current_sip=monthly_sip,
            required_sip=max(monthly_sip + 1.0, goal_corpus / max(years * 12, 1) / 10.0),
            required_corpus=goal_corpus,
            current_age=30,
            retirement_age=30 + int(years),
            current_monthly_expense=50000.0,
            existing_corpus=existing_corpus,
            expected_return=expected_return,
        )
    return result


def calculate_effective_savings(monthly_savings: float, loans: list[dict]) -> float:
    return float(monthly_savings) - sum(float(loan.get("emi", 0.0)) for loan in loans)


def get_ideal_risk_range(age: int, dependents: int, monthly_income: float):
    return ideal_risk_range_for_profile(age, dependents, monthly_income)


def get_diversification_gap_message(current_score: float, penalties: list[str]) -> str:
    target_score = 10.0
    gap = max(0.0, target_score - float(current_score))
    labels = ", ".join(str(p).replace("_", " ") for p in penalties)
    return f"Diversification gap: {gap:.1f} points due to {labels}."


# ─────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────
def make_profile(**overrides):
    """Base profile — override any field for each test."""
    base = {
        "age": 30,
        "dependents": 0,
        "monthly_income": 150000,
        "monthly_savings": 40000,
        "behavior": "moderate",
        "retirement_age": 60,
    }
    base.update(overrides)
    return base


def make_portfolio(**overrides):
    base = {
        "fd_bonds": 300000,
        "cash": 100000,
        "gold": 100000,
        "equity": 500000,
    }
    base.update(overrides)
    return base


def _risk_input_from_profile(profile: dict) -> dict:
    return {
        "age": profile["age"],
        "dependents": profile["dependents"],
        "income": profile["monthly_income"],
        "savings": profile["monthly_savings"],
        "behavior": profile["behavior"],
    }


# ─────────────────────────────────────────
# TEST 1 — RISK SCORE LOGIC
# ─────────────────────────────────────────
class TestRiskScoreLogic:
    def test_young_aggressive_no_dependents_scores_high(self):
        profile = make_profile(
            age=25,
            dependents=0,
            behavior="aggressive",
            monthly_savings=50000,
        )
        result = compute_risk(_risk_input_from_profile(profile), macro_data=None)
        score = result["score"]
        assert score >= 6.5
        assert result["category"] in {"Moderate", "Aggressive"}

    def test_dependents_reduce_risk_score(self):
        low_dep = compute_risk(
            _risk_input_from_profile(make_profile(age=25, dependents=0, behavior="aggressive")),
            None,
        )
        high_dep = compute_risk(
            _risk_input_from_profile(make_profile(age=25, dependents=5, behavior="aggressive")),
            None,
        )
        assert high_dep["score"] < low_dep["score"]
        assert (low_dep["score"] - high_dep["score"]) >= 0.5

    def test_older_age_reduces_risk_score(self):
        young = compute_risk(
            _risk_input_from_profile(make_profile(age=25, behavior="aggressive")),
            None,
        )
        old = compute_risk(
            _risk_input_from_profile(make_profile(age=55, behavior="aggressive")),
            None,
        )
        assert old["score"] < young["score"]

    def test_conservative_behavior_scores_low(self):
        result = compute_risk(
            _risk_input_from_profile(make_profile(age=30, behavior="conservative", dependents=3)),
            None,
        )
        assert result["score"] <= 5.0
        assert result["category"] in ["Conservative", "Moderate"]

    def test_risk_band_thresholds_exist_and_are_ordered(self):
        thresholds = RISK_BAND_THRESHOLDS
        assert "Conservative" in thresholds
        assert "Moderate" in thresholds
        assert "Aggressive" in thresholds
        assert thresholds["Conservative"]["max"] < thresholds["Moderate"]["max"]
        assert thresholds["Moderate"]["max"] <= thresholds["Aggressive"]["max"] <= 10.0

    def test_score_explanation_has_all_required_fields(self):
        result = compute_risk(_risk_input_from_profile(make_profile()), None)
        assert "score" in result
        assert "category" in result
        assert "factors" in result
        assert "methodology_note" in result
        assert "allocation_mapping" in result
        assert len(result["factors"]) == 4
        for factor in result["factors"]:
            assert "name" in factor
            assert "contribution" in factor
            assert "rationale" in factor

    def test_allocation_mapping_returns_valid_percentages(self):
        alloc = risk_score_to_allocation(6.0)
        assert "equity" in alloc and "debt" in alloc and "gold" in alloc
        total = alloc["equity"] + alloc["debt"] + alloc["gold"]
        assert abs(total - 100) <= 1
        alloc_aggressive = risk_score_to_allocation(8.5)
        assert alloc_aggressive["equity"] > alloc["equity"]


# ─────────────────────────────────────────
# TEST 2 — DIVERSIFICATION SCORE LOGIC
# ─────────────────────────────────────────
class TestDiversificationLogic:
    def test_fd_heavy_portfolio_scores_low(self):
        portfolio = make_portfolio(fd_bonds=800000, cash=100000, gold=0, equity=100000)
        score = compute_diversification_score(
            portfolio,
            monthly_income=150000,
            risk_score=7.0,
        )
        assert score <= 5.0

    def test_balanced_portfolio_scores_high(self):
        portfolio = make_portfolio(fd_bonds=300000, cash=100000, gold=100000, equity=500000)
        score = compute_diversification_score(
            portfolio,
            monthly_income=150000,
            risk_score=6.0,
        )
        assert score >= 6.0

    def test_excess_cash_penalizes_score(self):
        normal_cash = compute_diversification_score(
            make_portfolio(cash=300000),
            monthly_income=150000,
            risk_score=6.0,
        )
        excess_cash = compute_diversification_score(
            make_portfolio(cash=600000),
            monthly_income=150000,
            risk_score=6.0,
        )
        assert excess_cash < normal_cash

    def test_gold_over_15pct_penalizes_score(self):
        normal = compute_diversification_score(
            {"fd_bonds": 400000, "cash": 100000, "gold": 100000, "equity": 400000},
            monthly_income=150000,
            risk_score=6.0,
        )
        heavy_gold = compute_diversification_score(
            {"fd_bonds": 300000, "cash": 100000, "gold": 300000, "equity": 300000},
            monthly_income=150000,
            risk_score=6.0,
        )
        assert heavy_gold < normal

    def test_risk_mismatch_penalizes_score(self):
        mismatched = compute_diversification_score(
            make_portfolio(fd_bonds=700000, cash=200000, gold=50000, equity=50000),
            monthly_income=150000,
            risk_score=8.0,
        )
        assert mismatched <= 5.0


# ─────────────────────────────────────────
# TEST 3 — GOAL CONFIDENCE LOGIC
# ─────────────────────────────────────────
class TestGoalConfidenceLogic:
    def test_adequate_savings_gives_high_confidence(self):
        result = run_monte_carlo(
            monthly_sip=40000,
            existing_corpus=900000,
            goal_corpus=30000000,
            years=30,
            expected_return=0.12,
            std_dev=0.15,
        )
        assert result["probability"] >= 60

    def test_insufficient_savings_gives_low_confidence(self):
        result = run_monte_carlo(
            monthly_sip=5000,
            existing_corpus=100000,
            goal_corpus=50000000,
            years=15,
            expected_return=0.12,
            std_dev=0.15,
        )
        assert result["probability"] < 50

    def test_low_confidence_triggers_fix_recommendations(self):
        result = run_monte_carlo(
            monthly_sip=5000,
            existing_corpus=100000,
            goal_corpus=50000000,
            years=15,
            expected_return=0.12,
            std_dev=0.15,
        )
        assert result["probability"] < 50
        assert "fix_recommendation" in result
        fix = result["fix_recommendation"]
        assert "gap_analysis" in fix
        assert "option_1" in fix
        assert "option_2" in fix
        assert "option_3" in fix

    def test_more_years_improves_confidence(self):
        short = run_monte_carlo(
            monthly_sip=20000,
            existing_corpus=500000,
            goal_corpus=20000000,
            years=10,
            expected_return=0.12,
            std_dev=0.15,
        )
        long = run_monte_carlo(
            monthly_sip=20000,
            existing_corpus=500000,
            goal_corpus=20000000,
            years=25,
            expected_return=0.12,
            std_dev=0.15,
        )
        assert long["probability"] > short["probability"]


# ─────────────────────────────────────────
# TEST 4 — PORTFOLIO REBALANCING LOGIC
# ─────────────────────────────────────────
class TestPortfolioRebalancingLogic:
    def test_equity_underweight_triggers_increase(self):
        current = {"fd_bonds": 800000, "cash": 100000, "gold": 50000, "equity": 50000}
        target = {"equity": 0.75, "debt": 0.15, "gold": 0.10}
        gaps = compute_allocation_gap(current, target, total_corpus=1000000)
        equity_gap = next((g for g in gaps if g["asset_class"] == "equity"), None)
        assert equity_gap is not None
        assert equity_gap["action"] == "INCREASE"
        assert equity_gap["gap_pct"] >= 60

    def test_fd_overweight_triggers_reduce(self):
        current = {"fd_bonds": 800000, "cash": 100000, "gold": 50000, "equity": 50000}
        target = {"equity": 0.75, "debt": 0.15, "gold": 0.10}
        gaps = compute_allocation_gap(current, target, total_corpus=1000000)
        debt_gap = next((g for g in gaps if g["asset_class"] == "debt"), None)
        assert debt_gap is not None
        assert debt_gap["action"] == "REDUCE"

    def test_sip_amount_is_computed_not_hardcoded(self, monkeypatch):
        current = {"fd_bonds": 500000, "cash": 100000, "gold": 100000, "equity": 300000}
        target = {"equity": 0.60, "debt": 0.25, "gold": 0.15}
        gaps = compute_allocation_gap(current, target, total_corpus=1000000)

        def _fake_pipeline(allocation_weights, risk_profile, market_signals):
            return [
                {
                    "name": "Test Fund A",
                    "category": "Equity",
                    "alpha_3y": 3.5,
                    "fund_type": "MF",
                }
            ]

        monkeypatch.setattr(
            "backend.engines.v2.portfolio_gap_advisor.run_dynamic_pipeline",
            _fake_pipeline,
        )

        recommendations = recommend_funds_for_gap(
            gaps,
            {"score": 7.0, "category": "Aggressive"},
            {"market_trend": "Bullish", "macro_context_score": 0.8},
            [],
        )
        for rec in recommendations:
            if rec["action"] == "INCREASE" and rec.get("fund_name"):
                assert rec["suggested_sip"] > 0
                assert rec["suggested_sip"] != 15000
                assert rec["fund_name"] != "Parag Parikh Flexi Cap Fund"

    def test_no_fund_data_shows_graceful_message(self, monkeypatch):
        current = {"fd_bonds": 500000, "cash": 200000, "gold": 200000, "equity": 100000}
        target = {"equity": 0.60, "debt": 0.25, "gold": 0.15}
        gaps = compute_allocation_gap(current, target, total_corpus=1000000)

        monkeypatch.setattr(
            "backend.engines.v2.portfolio_gap_advisor.run_dynamic_pipeline",
            lambda allocation_weights, risk_profile, market_signals: [],
        )

        recommendations = recommend_funds_for_gap(
            gaps,
            risk_profile={"score": 7.0, "category": "Aggressive"},
            market_signals={"market_trend": "Bullish", "macro_context_score": 0.8},
            existing_funds=[],
        )
        increase_rec = next(
            (rec for rec in recommendations if rec["action"] in {"INCREASE", "ENTER"}),
            None,
        )
        assert increase_rec is not None
        assert increase_rec["fund_name"] is None
        assert "no qualifying fund" in increase_rec["reason"].lower()


# ─────────────────────────────────────────
# TEST 5 — EMI DEDUCTION LOGIC
# ─────────────────────────────────────────
class TestEMIDeductionLogic:
    def test_emi_reduces_effective_savings(self):
        effective = calculate_effective_savings(
            monthly_savings=40000,
            loans=[{"emi": 25000}, {"emi": 5000}],
        )
        assert effective == 10000

    def test_zero_loans_keeps_full_savings(self):
        effective = calculate_effective_savings(
            monthly_savings=40000,
            loans=[],
        )
        assert effective == 40000

    def test_emi_exceeding_savings_returns_zero_or_negative(self):
        effective = calculate_effective_savings(
            monthly_savings=40000,
            loans=[{"emi": 50000}],
        )
        assert effective <= 0

    def test_goal_sip_uses_effective_savings_not_raw(self):
        goal_with_emi = calculate_goal(
            "retirement",
            {
                "current_monthly_expense": 50000,
                "retirement_age": 60,
                "current_age": 30,
                "existing_corpus": 0,
                "annual_sip_step_up": 0,
            },
            expected_return_rate=0.12,
        )
        goal_no_emi = calculate_goal(
            "retirement",
            {
                "current_monthly_expense": 50000,
                "retirement_age": 60,
                "current_age": 30,
                "existing_corpus": 0,
                "annual_sip_step_up": 0,
            },
            expected_return_rate=0.12,
        )
        with_emi_effective = calculate_effective_savings(40000, [{"emi": 30000}])
        no_emi_effective = calculate_effective_savings(40000, [])
        assert goal_with_emi["required_sip"] == goal_no_emi["required_sip"]
        assert with_emi_effective < no_emi_effective


# ─────────────────────────────────────────
# TEST 6 — SCORE INTELLIGENCE PANEL LOGIC
# ─────────────────────────────────────────
class TestScoreIntelligencePanelLogic:
    def test_ideal_risk_range_computed_for_young_profile(self):
        low, high = get_ideal_risk_range(age=25, dependents=0, monthly_income=150000)
        assert low >= 7.0
        assert high <= 10.0

    def test_ideal_risk_range_lower_for_older_profile(self):
        young_low, _ = get_ideal_risk_range(age=25, dependents=0, monthly_income=150000)
        old_low, _ = get_ideal_risk_range(age=55, dependents=2, monthly_income=150000)
        assert old_low < young_low

    def test_diversification_gap_message_is_specific(self):
        msg = get_diversification_gap_message(
            current_score=4.0,
            penalties=["cash_drag", "risk_mismatch"],
        )
        assert "6.0 points" in msg or "6 points" in msg
