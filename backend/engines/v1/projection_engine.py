import pandas as pd
from typing import List, Dict, Any


def generate_projection_table(
    initial_investment: float, monthly_sip: float, annual_return_rate: float, years: int
) -> pd.DataFrame:
    """
    Generate a yearly growth table showing projection details.
    Columns: year | invested | returns | total_value

    Args:
        initial_investment (float): Starting lumpsum investment.
        monthly_sip (float): Monthly additional investment.
        annual_return_rate (float): Expected annual return rate.
        years (int): Duration in years.

    Returns:
        pd.DataFrame: DataFrame containing the yearly projection.
    """
    monthly_rate = annual_return_rate / 12.0

    data: List[Dict[str, Any]] = []

    current_value = initial_investment
    cumulative_invested = initial_investment

    for year in range(1, years + 1):
        for month in range(12):
            # Invest at beginning of month
            current_value += monthly_sip
            cumulative_invested += monthly_sip

            # Returns compounded monthly
            month_return = current_value * monthly_rate
            current_value += month_return

        data.append(
            {
                "year": year,
                "invested": round(cumulative_invested, 2),
                "returns": round(current_value - cumulative_invested, 2),
                "total_value": round(current_value, 2),
            }
        )

    return pd.DataFrame(data)
