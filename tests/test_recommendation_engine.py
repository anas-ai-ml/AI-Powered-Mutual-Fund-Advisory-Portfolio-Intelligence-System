import pytest
import pandas as pd
from backend.engines.recommendation_engine.quality_filter import apply_quality_filter
from backend.engines.recommendation_engine.scoring_engine import score_funds
from backend.engines.recommendation_engine.user_matching import apply_user_matching
from backend.engines.recommendation_engine.dynamic_recommender import run_dynamic_pipeline

@pytest.fixture
def mock_fund_data():
    return pd.DataFrame([
        {
            "scheme_name": "Good Large Cap Fund",
            "category": "Equity - Large Cap",
            "expense_ratio": 0.5,
            "aum_crore": 10000,
            "1y": 15.0,
            "3y": 12.0,
            "5y": 14.0,
            "volatility": 0.10
        },
        {
            "scheme_name": "Bad Expensive Fund",
            "category": "Equity - Large Cap",
            "expense_ratio": 2.5,
            "aum_crore": 10000,
            "1y": 15.0,
            "3y": 12.0,
            "5y": 14.0,
            "volatility": 0.10
        },
        {
            "scheme_name": "Small Cap High Risk",
            "category": "Equity - Small Cap",
            "expense_ratio": 1.0,
            "aum_crore": 2000,
            "1y": 30.0,
            "3y": 25.0,
            "5y": 20.0,
            "volatility": 0.25
        },
        {
            "scheme_name": "Negative Return Fund",
            "category": "Equity - Mid Cap",
            "expense_ratio": 1.0,
            "aum_crore": 2000,
            "1y": -5.0,
            "3y": -2.0,
            "5y": -1.0,
            "volatility": 0.15
        }
    ])

def test_quality_filter(mock_fund_data):
    filtered = apply_quality_filter(mock_fund_data)
    # Should drop "Bad Expensive Fund" (ER 2.5) and "Negative Return Fund" (3Y < 0)
    assert len(filtered) == 2
    names = filtered["scheme_name"].tolist()
    assert "Good Large Cap Fund" in names
    assert "Small Cap High Risk" in names
    assert "Bad Expensive Fund" not in names
    assert "Negative Return Fund" not in names

def test_scoring_engine(mock_fund_data):
    df = apply_quality_filter(mock_fund_data)
    signals = {"market_trend": "bullish", "volatility": "low"}
    scored = score_funds(df, signals)
    
    # Check that score is calculated
    assert "score" in scored.columns
    # Small cap should receive bullish market fit boost
    small_cap = scored[scored["category"] == "Equity - Small Cap"].iloc[0]
    assert small_cap["market_fit"] >= 0.8
    assert small_cap["score"] > 0

def test_user_matching(mock_fund_data):
    # Conservative should drop Small Cap
    df = apply_quality_filter(mock_fund_data)
    cons_df = apply_user_matching(df, "Conservative")
    assert "Small Cap High Risk" not in cons_df["scheme_name"].tolist()
    assert "Good Large Cap Fund" in cons_df["scheme_name"].tolist()

    # Aggressive keeps Small Cap
    agg_df = apply_user_matching(df, "Aggressive")
    assert "Small Cap High Risk" in agg_df["scheme_name"].tolist()
