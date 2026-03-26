import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from backend.data.data_loader import get_all_funds_data


def train_and_predict_returns(df: pd.DataFrame, current_nav: float) -> dict:
    """
    Fits a simple Linear Regression on historical log-returns
    to trend future NAVs. Returns forecasted 1Y, 3Y,
    and 5Y annualized returns.
    """
    # Calculate daily returns and cumulative log returns
    df = df.sort_values("Date").copy()
    df["DayIndex"] = (df["Date"] - df["Date"].min()).dt.days
    df["LogNAV"] = np.log(df["Close"])

    # Prepare training data (X = Time, y = Log NAV)
    X = df[["DayIndex"]].values
    y = df["LogNAV"].values

    # Fit Linear Trend to find the compound average growth rate
    model = LinearRegression()
    model.fit(X, y)

    # Get the daily log return slope
    _ = model.coef_[0]  # daily_growth_rate (conceptual)

    # Conceptually, to get annualized return from daily log return slope:
    # Annual Growth = (e^(daily_growth_rate * 252)) - 1
    # We will compute the projected NAV in 1, 3, and 5 years directly.

    last_day = df["DayIndex"].max()

    def predict_future_return(years: int) -> float:
        future_day = last_day + (years * 365.25)
        projected_log_nav = model.predict([[future_day]])[0]
        projected_nav = np.exp(projected_log_nav)

        # Calculate raw point-to-point percentage return
        total_return = (projected_nav - current_nav) / current_nav

        # Annualize it
        annualized_return = ((1 + total_return) ** (1 / years)) - 1
        return round(annualized_return * 100, 2)

    return {
        "1y": predict_future_return(1),
        "3y": predict_future_return(3),
        "5y": predict_future_return(5),
    }


def build_predictive_database() -> list:
    """
    Fetches real data and builds a dynamic fund database
    with AI-predicted returns.
    """
    raw_data = get_all_funds_data()
    dynamic_database = []

    for ticker, info in raw_data.items():
        df = info["data"]
        if len(df) < 252:  # Need at least ~1 yr of data
            continue

        current_nav = df.iloc[-1]["Close"]
        predictions = train_and_predict_returns(df, current_nav)

        # Determine rough Risk Level based on standard deviation of daily returns
        daily_returns = df["Close"].pct_change().dropna()
        annual_volatility = daily_returns.std() * np.sqrt(252) * 100

        if annual_volatility < 5:
            risk = "Low"
        elif annual_volatility < 12:
            risk = "Moderate"
        else:
            risk = "High"

        # Extract a clean name from the ticker proxy
        name_map = {
            "0P00005WZY.BO": "ICICI Prudential Bluechip Fund",
            "0P0000XVMA.BO": "Parag Parikh Flexi Cap Fund",
            "0P00005WVT.BO": "HDFC Flexi Cap Fund",
            "0P00005WZZ.BO": "SBI Equity Hybrid Fund",
            "LIQUIDBEES.NS": "Nippon India Liquid ETF",
            "GOLDBEES.NS": "Nippon India Gold ETF",
        }

        clean_name = name_map.get(ticker, ticker)

        dynamic_database.append(
            {
                "name": clean_name,
                "category": info["category"],
                "risk": risk,
                "1y": predictions["1y"],
                "3y": predictions["3y"],
                "5y": predictions["5y"],
            }
        )

    return dynamic_database


if __name__ == "__main__":
    db = build_predictive_database()
    for fund in db:
        print(f"{fund['name']} ({fund['category']}) - {fund['risk']} Risk:")
        print(
            f"  Projected Returns -> 1Y: {fund['1y']}%, 3Y: {fund['3y']}%, 5Y: {fund['5y']}%"
        )
