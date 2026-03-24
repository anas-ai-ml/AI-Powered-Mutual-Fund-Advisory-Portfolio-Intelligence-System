from typing import Dict, Any

def analyze_portfolio(
    existing_fd: float,
    existing_savings: float,
    existing_gold: float,
    existing_mutual_funds: float,
    risk_score: float = 5.0,
    monthly_income: float = 0.0,
) -> Dict[str, Any]:
    """
    Analyzes the existing asset distribution, computes risk alignment,
    quantifies cash drag, and generates dynamic insights.
    """
    total_corpus = (
        existing_fd + existing_savings + existing_gold + existing_mutual_funds
    )

    if total_corpus == 0:
        return {
            "total_corpus": 0.0,
            "diversification_score": 0,
            "risk_exposure": "N/A (No Investments)",
            "insights": ["Start investing to build a portfolio. You currently have no deployed assets."],
            "breakdown": {},
        }

    breakdown = {
        "Fixed Deposits / Bonds": round((existing_fd / total_corpus) * 100, 2),
        "Savings / Cash": round((existing_savings / total_corpus) * 100, 2),
        "Gold": round((existing_gold / total_corpus) * 100, 2),
        "Mutual Funds / Equity": round((existing_mutual_funds / total_corpus) * 100, 2),
    }

    score = 10
    insights = []

    # 1. Quantified Cash Drag Analysis
    # Assume 3 months of income is a healthy emergency fund. Rest is cash drag.
    emergency_fund_required = monthly_income * 3
    if existing_savings > emergency_fund_required and emergency_fund_required > 0:
        excess_cash = existing_savings - emergency_fund_required
        # Assume an opportunity cost of 7% (12% Equity - 5% Savings)
        lost_returns = excess_cash * 0.07 
        score -= 2
        insights.append(
            f"High Cash Drag: You are holding exactly ₹{excess_cash:,.0f} in excess idle cash "
            f"beyond a 3-month emergency fund (₹{emergency_fund_required:,.0f}). Deploying this "
            f"excess cash into the market could yield an extra ₹{lost_returns:,.0f} annually."
        )
    elif existing_savings < monthly_income * 1 and monthly_income > 0:
        score -= 1
        insights.append(
            f"Low Liquidity Warning: You have less than 1 month of income in liquid cash. "
            f"Consider diverting some SIPs to build a ₹{emergency_fund_required:,.0f} emergency fund."
        )
    elif existing_savings > 0 and monthly_income == 0:
        # Prevent math errors if monthly_income is 0
        if breakdown["Savings / Cash"] > 20:
             score -= 1
             insights.append("High cash drag. Consider moving excess savings to liquid funds or short-term debt.")

    # Calculate actual equity exposure
    equity_exposure = breakdown["Mutual Funds / Equity"]
    
    if equity_exposure < 30:
        actual_risk = "Conservative"
        actual_risk_val = 3
    elif equity_exposure <= 60:
        actual_risk = "Moderate"
        actual_risk_val = 6
    else:
        actual_risk = "Aggressive"
        actual_risk_val = 9

    # 2. Risk Alignment Check
    # risk_score (0-10) is the ML prediction of their capacity
    if risk_score >= 7.5 and actual_risk_val <= 3:
        # Aggressive capacity, but behaving conservatively
        score -= 2
        insights.append(
            f"Risk Mismatch: Your theoretical risk profile is Highly Aggressive (Score: {risk_score}), "
            f"but your actual portfolio is structurally Conservative ({equity_exposure}% Equity). "
            "You are mathematically leaving significant long-term compounding wealth on the table."
        )
    elif risk_score <= 4.0 and actual_risk_val >= 9:
        # Conservative capacity, but behaving aggressively
        score -= 3
        insights.append(
            f"Risk Mismatch: Your theoretical risk profile is Conservative (Score: {risk_score}), "
            f"but your actual portfolio is Highly Aggressive ({equity_exposure}% Equity). "
            "You are heavily over-exposed to severe market drawdowns."
        )
    elif breakdown["Mutual Funds / Equity"] < 20:
        score -= 1
        insights.append(
            "Low overall equity exposure structurally limits long-term compounding wealth creation. "
            "Consider scaling into diversified Index or Large Cap funds."
        )

    # 3. Specific Asset Classes Warning
    if breakdown["Gold"] > 15:
        score -= 1
        insights.append(
            f"Gold Allocation High ({breakdown['Gold']}%): Precious metals should be limited to 5-10% "
            "purely for inflation hedging. The excess is a non-yielding drag."
        )

    if breakdown["Fixed Deposits / Bonds"] > 60:
        score -= 2
        insights.append(
            f"Fixed Income Heavy ({breakdown['Fixed Deposits / Bonds']}%): Over 60% of your net worth is in FDs. "
            "These are highly tax-inefficient and historically fail to beat real post-tax inflation."
        )

    if score >= 9:
        insights.append(
            "Portfolio Health Optimal: Your deployed asset allocation mathematically aligns perfectly "
            "with efficient diversification metrics tailored to you."
        )

    return {
        "total_corpus": total_corpus,
        "diversification_score": max(0, score),
        "risk_exposure": f"{actual_risk} ({equity_exposure}% Equity)",
        "insights": insights,
        "breakdown": breakdown,
    }
