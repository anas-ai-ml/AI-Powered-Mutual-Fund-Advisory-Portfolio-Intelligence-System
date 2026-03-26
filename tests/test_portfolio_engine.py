from backend.engines.portfolio_engine import analyze_portfolio


def test_portfolio_engine_generates_cash_drag_insight():
    result = analyze_portfolio(
        existing_fd=200000,
        existing_savings=600000,
        existing_gold=50000,
        existing_mutual_funds=150000,
        risk_score=6.0,
        monthly_income=100000,
        current_cpi=6.0,
        goal_years=10,
    )
    messages = [item["message"] for item in result["prioritized_insights"]]
    assert any("savings/cash" in message for message in messages)


def test_portfolio_engine_generates_risk_mismatch_insight():
    result = analyze_portfolio(
        existing_fd=500000,
        existing_savings=100000,
        existing_gold=50000,
        existing_mutual_funds=100000,
        risk_score=8.0,
        monthly_income=100000,
        current_cpi=5.5,
        goal_years=20,
    )
    severities = [item["severity"] for item in result["prioritized_insights"]]
    assert "high" in severities
