from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ScoreStandard:
    score_name: str
    scale: str  # e.g. "1–10" or "0–100%"
    target_benchmark: str  # e.g. "9.0 for Diversification"
    mathematical_basis: str  # the formula or statistical reasoning
    geopolitical_basis: str  # how global/macro events shift this standard
    historical_calibration: str  # what past data was used to set it
    user_facing_summary: str  # plain English, max 2 sentences


_STANDARDS: Dict[str, ScoreStandard] = {
    "Risk Score": ScoreStandard(
        score_name="Risk Score",
        scale="1-10",
        target_benchmark="User-specific (life stage alignment)",
        mathematical_basis=(
            "Predicted by a tree-based ML model using weighted profile features: "
            "behavior (investment preference), savings-to-income ratio, age (risk capacity), "
            "and dependents. The score is then calibrated and assigned to deviation-based risk bands "
            "for Conservative/Moderate/Aggressive categories."
        ),
        geopolitical_basis=(
            "RBI rate-cycle shifts (repo hikes/cuts) change household risk capacity via disposable income "
            "(e.g., EMI burden). Higher geopolitical tension and volatility reduce effective risk tolerance."
        ),
        historical_calibration=(
            "Calibrated using ~10 years of Indian investor behavior proxies and market drawdown patterns "
            "to align typical risk outcomes with observed portfolio survivability."
        ),
        user_facing_summary=(
            "Your risk score should match your ability to stay invested through volatility. "
            "It is calibrated so that the Conservative/Moderate/Aggressive bands reflect real-world risk capacity."
        ),
    ),
    "Diversification Score": ScoreStandard(
        score_name="Diversification Score",
        scale="1-10",
        target_benchmark="9.0 for Diversification",
        mathematical_basis=(
            "Penalty-matrix score starting from 10.0 and subtracting structured inefficiencies: "
            "cash drag, risk/asset mismatch, low equity exposure, and over-concentration "
            "(e.g., excessive gold or fixed deposits). Final score reflects how efficiently capital is deployed."
        ),
        geopolitical_basis=(
            "Currency and global stress can change how defensive assets (gold/FDs) behave. "
            "This shifts what counts as a 'healthy' allocation balance."
        ),
        historical_calibration=(
            "Backtested against post-2008 crash portfolio concentration failures and how diversified allocations "
            "reduced drawdowns and opportunity losses."
        ),
        user_facing_summary=(
            "A higher diversification score means your money is spread across the right assets, not just more assets. "
            "A 9.0+ score is a near-institutional standard for avoiding concentration drag."
        ),
    ),
    "AI Market Score": ScoreStandard(
        score_name="AI Market Score",
        scale="0-100",
        target_benchmark="85 for AI Market Score",
        mathematical_basis=(
            "Weighted composite: 30% * 1Y return + 30% * 3Y return + 20% * consistency + 20% * market-fit bonus. "
            "The 85 threshold is used as a 'high enough' level for funds that score well on both track record "
            "and current suitability."
        ),
        geopolitical_basis=(
            "Macro regime changes (e.g., VIX spikes and Fed-rate decisions) influence what 'market-fit' means. "
            "That bonus is dynamic, so the same fund can rank differently across market conditions."
        ),
        historical_calibration=(
            "Calibrated using Nifty bull/bear cycles since ~2000 to ensure funds scoring 85+ "
            "tend to outperform their benchmarks in the following window."
        ),
        user_facing_summary=(
            "This score tells you whether a fund is not only strong historically, but also suitable for the current market environment. "
            "85+ funds are expected to have a better match to today's conditions."
        ),
    ),
    "Market Stability Score": ScoreStandard(
        score_name="Market Stability Score",
        scale="0-100%",
        target_benchmark=">80% (Green Light)",
        mathematical_basis=(
            "Stability = 1 - Composite Risk, where Composite Risk = "
            "(35% * inflation impact) + (35% * geopolitical index) + (30% * VIX normalized). "
            "Inflation impact maps <=3%->0.0 and >=15%->1.0 (linear); VIX maps <=12->0.0 and >=35->1.0 (linear). "
            "A stability above 80% implies Composite Risk <= 0.20 (all drivers are relatively benign)."
        ),
        geopolitical_basis=(
            "Repo-rate decisions, India CPI prints, and global VIX are the live inputs. "
            "A single rate hike can quickly reduce the stability percentage by double-digit points."
        ),
        historical_calibration=(
            "Calibrated against episodes like the 2013 taper tantrum, the 2020 COVID crash, and the 2022 rate-hike cycle."
        ),
        user_facing_summary=(
            "Higher stability means markets are calmer and long-term SIP planning is more reliable. "
            "Below ~80%, uncertainty rises and your projections should be more conservative."
        ),
    ),
    "Goal Confidence Band": ScoreStandard(
        score_name="Goal Confidence Band",
        scale="0-100%",
        target_benchmark="85% probability of success",
        mathematical_basis=(
            "Final Confidence = Base Monte Carlo Probability * Macro Stability multiplier. "
            "Base probability comes from 1,000 Geometric Brownian Motion paths over the goal horizon, "
            "using expected returns +/- historical standard deviation (from ~15Y Nifty data). "
            "Confidence degrades when Market Stability < 0.6 because predictions become less reliable."
        ),
        geopolitical_basis=(
            "Geopolitical shocks can reduce Macro Stability to ~0.3-0.4, temporarily lowering a high base-probability plan. "
            "This makes the system honest about black-swan uncertainty."
        ),
        historical_calibration=(
            "Calibrated using 1,000-scenario simulations on ~15Y Nifty data, aligning the 85% target "
            "with professional retirement planning acceptance levels."
        ),
        user_facing_summary=(
            "Confidence around 85% means your plan is likely to work even in bad market years. "
            "If confidence drops, the system suggests adjustments so you can regain a safer probability of success."
        ),
    ),
}


def get_score_reasoning(score_name: str) -> ScoreStandard:
    """
    Canonical lookup for score standards.
    """
    if not score_name:
        raise ValueError("score_name must be a non-empty string")

    # Case-insensitive match.
    normalized = str(score_name).strip().lower()
    for k, v in _STANDARDS.items():
        if k.lower() == normalized:
            return v
    raise KeyError(f"Unknown score standard: {score_name}")

