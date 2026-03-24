import numpy as np

def run_monte_carlo_simulation(
    initial_corpus: float,
    monthly_sip: float,
    years: int,
    target_corpus: float,
    expected_annual_return: float,
    annual_volatility: float = 0.12,
    num_simulations: int = 1000,
) -> float:
    """
    Run a Monte Carlo simulation using Geometric Brownian Motion (GBM) 
    to calculate the probability of achieving the target corpus.
    """
    if years <= 0 or target_corpus <= 0:
        return 0.0

    months = years * 12
    dt = 1.0 / 12.0

    success_count = 0
    np.random.seed(42)  # For reproducibility in testing

    # GBM Parameters drift and diffusion
    # Drift: (mu - sigma^2 / 2) * dt
    drift = (expected_annual_return - (annual_volatility ** 2) / 2) * dt
    
    # Pre-compute random diffusion matrix for all paths
    diffusion = annual_volatility * np.sqrt(dt) * np.random.normal(size=(num_simulations, months))

    # Calculate compounded return multipliers
    return_multipliers = np.exp(drift + diffusion)

    for i in range(num_simulations):
        current_corpus = initial_corpus
        for month in range(months):
            current_corpus += monthly_sip
            # Apply GBM growth
            current_corpus *= return_multipliers[i, month]

        if current_corpus >= target_corpus:
            success_count += 1

    success_probability = (success_count / num_simulations) * 100.0

    return round(success_probability, 2)
