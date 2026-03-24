import pytest
from backend.engines.risk_engine import calculate_risk_score


def test_risk_score_boundaries():
    """Test that extreme profiles categorize correctly."""
    # Aggressive
    res1 = calculate_risk_score(
        age=25,
        dependents=0,
        behavior="high risk",
        monthly_income=100000,
        monthly_savings=50000,
    )
    assert res1["score"] > 7
    assert "Aggressive" in res1["category"]  # e.g. "Aggressive (ML Pred)"

    # Conservative
    res2 = calculate_risk_score(
        age=60,
        dependents=3,
        behavior="stability",
        monthly_income=50000,
        monthly_savings=2000,
    )
    assert res2["score"] < 5
    assert "Conservative" in res2["category"]  # e.g. "Conservative (ML Pred)"
