from typing import Dict, Any
import numpy as np
from scipy.optimize import minimize
from backend.data.market_data_fetcher import MarketDataFetcher

# Initialize fetcher once
fetcher = MarketDataFetcher()
# Attempt to load or compute stats
stats, corr_matrix = fetcher.compute_statistics()


def get_asset_allocation(risk_score: float) -> Dict[str, Any]:
    """
    Returns the dynamically optimized asset allocation based on the risk score using MPT.
    Risk score (0-10) is mapped to a target volatility constraint.
    """
    assets = list(stats.keys())
    returns = np.array([stats[a]["return"] for a in assets])
    vols = np.array([stats[a]["volatility"] for a in assets])

    n_assets = len(assets)

    # Construct Covariance Matrix
    if not corr_matrix.empty and corr_matrix.shape == (n_assets, n_assets):
        cov_matrix = np.outer(vols, vols) * corr_matrix.values
    else:
        # Fallback to zero correlation if live data failed
        cov_matrix = np.diag(vols**2)

    # Map Risk Score (0-10) to Target Volatility (4% to 20%)
    risk_score = max(0, min(10, risk_score))
    target_volatility = 0.04 + (risk_score / 10.0) * (0.24 - 0.04)

    # Objective: Minimize negative return (Maximize Return)
    def objective(weights):
        return -np.dot(weights, returns)

    # Constraints
    def vol_constraint(weights):
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        return target_volatility - port_vol  # must be >= 0

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},  # Sum of weights = 1
        {"type": "ineq", "fun": vol_constraint},  # Vol <= Target
    ]

    # Bounds: Enforce structural diversification
    bounds = []
    for asset in assets:
        if "Gold" in asset:
            bounds.append((0.0, 0.15))  # Max 15% Gold
        elif "Debt" in asset:
            if risk_score >= 7.5:
                bounds.append((0.0, 0.20))  # Aggressive: low debt cap
            elif risk_score <= 4.0:
                bounds.append((0.20, 1.0))  # Conservative: min 20% debt
            else:
                bounds.append((0.05, 1.0))
        elif "Small Cap" in asset or "Sectoral" in asset:
            bounds.append((0.0, 0.25))  # Cap highly volatile segments
        else:
            bounds.append((0.0, 0.40))  # Cap standard equities at 40% each

    # Initial guess: equal weight
    init_guess = np.array([1.0 / n_assets] * n_assets)

    # Optimization
    result = minimize(
        objective, init_guess, method="SLSQP", bounds=bounds, constraints=constraints
    )

    if result.success:
        optimal_weights = result.x
    else:
        # Fallback to equal weights if optimization fails
        optimal_weights = init_guess

    # Format output
    allocation = {}
    for asset, weight in zip(assets, optimal_weights):
        pct = round(weight * 100, 2)
        if pct > 0.01:
            allocation[asset] = pct

    # Re-normalize just in case due to rounding
    total = sum(allocation.values())
    if total > 0:
        for k in allocation:
            allocation[k] = round((allocation[k] / total) * 100, 2)

    if risk_score < 5:
        category = "Conservative"
    elif 5 <= risk_score <= 7:
        category = "Moderate"
    else:
        category = "Aggressive"

    return {"category": f"{category} (Optimized MPT)", "allocation": allocation}


if __name__ == "__main__":
    print(get_asset_allocation(8.0))


def adjust_allocation_for_volatility(base_alloc, target_volatility):
    equity_vol = 18
    debt_vol = 6
    gold_vol = 12

    current_vol = (
        base_alloc["equity"] * equity_vol
        + base_alloc["debt"] * debt_vol
        + base_alloc["gold"] * gold_vol
    ) / 100

    factor = target_volatility / current_vol

    base_alloc["equity"] *= factor
    base_alloc["debt"] *= 2 - factor

    total = sum(base_alloc.values())
    for k in base_alloc:
        base_alloc[k] = round((base_alloc[k] / total) * 100, 2)

    return base_alloc


def apply_macro_adjustment(allocation, regime):
    if regime == "HIGH_RISK":
        allocation["equity"] -= 10
        allocation["gold"] += 5

    elif regime == "LOW_RISK":
        allocation["equity"] += 5

    total = sum(allocation.values())
    return {k: round(v / total * 100, 2) for k, v in allocation.items()}
