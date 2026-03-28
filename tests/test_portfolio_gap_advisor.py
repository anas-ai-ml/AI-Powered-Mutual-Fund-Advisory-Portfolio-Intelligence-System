from backend.engines.v2.portfolio_gap_advisor import PortfolioGapAdvisor


def test_compute_allocation_gap_maps_cash_and_fd_to_debt():
    advisor = PortfolioGapAdvisor()
    gaps = advisor.compute_allocation_gap(
        current_portfolio={
            "fd_bonds": 500000,
            "gold": 100000,
            "cash": 200000,
            "equity": 100000,
        },
        target_allocation={"equity": 0.70, "debt": 0.20, "gold": 0.10},
        total_corpus=900000,
    )

    assert gaps == [
        {
            "asset_class": "equity",
            "current_pct": 11.11,
            "target_pct": 70.0,
            "gap_pct": 58.89,
            "gap_amount": 530000.0,
            "action": "INCREASE",
        },
        {
            "asset_class": "debt",
            "current_pct": 77.78,
            "target_pct": 20.0,
            "gap_pct": -57.78,
            "gap_amount": -520000.0,
            "action": "REDUCE",
        },
        {
            "asset_class": "gold",
            "current_pct": 11.11,
            "target_pct": 10.0,
            "gap_pct": -1.11,
            "gap_amount": -10000.0,
            "action": "REDUCE",
        },
    ]


def test_compute_allocation_gap_uses_exit_and_maintain_actions():
    advisor = PortfolioGapAdvisor(tolerance_pct=0.5)
    gaps = advisor.compute_allocation_gap(
        current_portfolio={"fd_bonds": 100000, "gold": 0, "cash": 0, "equity": 0},
        target_allocation={"debt": 0.0, "gold": 0.0},
        total_corpus=100000,
    )

    assert gaps == [
        {
            "asset_class": "debt",
            "current_pct": 100.0,
            "target_pct": 0.0,
            "gap_pct": -100.0,
            "gap_amount": -100000.0,
            "action": "EXIT",
        }
    ]

    maintain = advisor.compute_allocation_gap(
        current_portfolio={"fd_bonds": 200000, "gold": 100000, "cash": 0, "equity": 700000},
        target_allocation={"equity": 70.0, "debt": 20.0, "gold": 10.0},
        total_corpus=1000000,
    )
    assert [item["action"] for item in maintain] == ["MAINTAIN", "MAINTAIN", "MAINTAIN"]


def test_recommend_funds_for_gap_handles_increase_and_reduce_paths(monkeypatch):
    advisor = PortfolioGapAdvisor()
    gap_list = [
        {
            "asset_class": "equity",
            "current_pct": 11.11,
            "target_pct": 70.0,
            "gap_pct": 58.89,
            "gap_amount": 530000.0,
            "action": "INCREASE",
        },
        {
            "asset_class": "debt",
            "current_pct": 77.78,
            "target_pct": 20.0,
            "gap_pct": -57.78,
            "gap_amount": -520000.0,
            "action": "REDUCE",
        },
    ]

    def _fake_pipeline(allocation_weights, risk_profile, market_signals):
        assert allocation_weights == {"Equity": 100.0}
        assert risk_profile == "Aggressive"
        return [
            {
                "name": "Parag Parikh Flexi Cap Fund",
                "category": "Flexi",
                "alpha_3y": 4.2,
            }
        ]

    monkeypatch.setattr(
        "backend.engines.v2.portfolio_gap_advisor.run_dynamic_pipeline",
        _fake_pipeline,
    )

    recommendations = advisor.recommend_funds_for_gap(
        gap_list=gap_list,
        risk_profile={"category": "Aggressive"},
        market_signals={"market_trend": "bullish"},
        existing_funds=[
            {
                "name": "Bank FD Ladder",
                "category": "Debt",
                "current_value": 500000,
                "alpha_3y": 0.0,
            }
        ],
    )

    assert recommendations[0] == {
        "action": "INCREASE",
        "asset_class": "equity",
        "fund_name": "Parag Parikh Flexi Cap Fund",
        "category": "Flexi",
        "reason": "Your equity allocation (11%) is 59% below your target (70%) given your Aggressive risk profile.",
        "suggested_sip": 44166.67,
        "suggested_lumpsum": 530000.0,
        "urgency": "high",
        "benchmark_alpha": 4.2,
        "replaces": None,
        "rebalance_note": "Deploy ₹530,000 over the next 12 months to move equity closer to target.",
    }
    assert recommendations[1] == {
        "action": "REDUCE",
        "asset_class": "debt",
        "fund_name": "Bank FD Ladder",
        "category": "Debt",
        "reason": "Your debt allocation (78%) is 58% above your target (20%) given your Aggressive risk profile.",
        "suggested_sip": 0.0,
        "suggested_lumpsum": 0.0,
        "urgency": "high",
        "benchmark_alpha": 0.0,
        "replaces": "Bank FD Ladder",
        "rebalance_note": "Consider redeeming ₹520,000 from Bank FD Ladder and redeploying ₹520,000 to equity.",
    }
