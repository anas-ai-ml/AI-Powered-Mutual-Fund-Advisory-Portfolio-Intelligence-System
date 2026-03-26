import pytest
from backend.engines.goal_engine import (
    calculate_retirement_goal,
    calculate_child_education_goal,
    calculate_required_step_up_sip,
    calculate_sip_topup,
)


def test_retirement_goal():
    """Test retirement planning baseline values."""
    res = calculate_retirement_goal(30, 50000, 0.12)
    assert res["years_to_goal"] == 30
    assert res["future_corpus"] > 0
    assert res["required_sip"] > 0
    assert "sip_comparison" in res
    assert (
        res["sip_comparison"]["step_up"]["monthly_sip_year_1"]
        == res["required_sip"]
    )


def test_retirement_goal_with_post_retirement_income():
    """Retirement goal can optionally include distribution-phase income planning."""
    res = calculate_retirement_goal(
        30,
        50000,
        0.12,
        post_retirement_income=75000,
        post_retirement_years=25,
        include_post_retirement_income=True,
    )
    assert res["post_retirement_income_planning_enabled"] is True
    assert res["distribution_phase"]["annuity_corpus_required"] > 0
    assert "additional_sip_required" in res["distribution_phase"]


def test_child_education_goal():
    """Test child education goal calculation."""
    res = calculate_child_education_goal(2000000, 12, 0.12, annual_sip_step_up=0.10)
    assert res["years_to_goal"] == 12
    assert res["future_corpus"] > 2000000
    assert res["sip_comparison"]["step_up"]["monthly_sip_year_1"] < res["required_sip"]


def test_required_step_up_sip_reaches_target_future_value():
    target = 2500000
    starting_sip = calculate_required_step_up_sip(
        target_future_value=target,
        annual_step_up=0.10,
        years=12,
        return_rate=0.12,
    )
    result = calculate_sip_topup(
        current_sip=starting_sip,
        annual_step_up=0.10,
        years=12,
        return_rate=0.12,
    )
    assert abs(result["future_value"] - target) < 5
