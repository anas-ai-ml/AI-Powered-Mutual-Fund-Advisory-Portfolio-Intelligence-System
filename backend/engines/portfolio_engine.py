from typing import Dict, Any, List

from backend.engines.risk_engine import risk_score_to_allocation


class PortfolioInsightEngine:
    def __init__(
        self,
        asset_allocation: Dict[str, float],
        total_corpus: float,
        monthly_income: float,
        risk_score: float,
        current_cpi: float,
        goal_years: int,
        term_life_cover: float = 0.0,
        annual_income: float = 0.0,
        emi_total: float = 0.0,
    ):
        self.asset_allocation = asset_allocation
        self.total_corpus = float(total_corpus)
        self.monthly_income = float(monthly_income)
        self.risk_score = float(risk_score)
        self.current_cpi = float(current_cpi)
        self.goal_years = max(1, int(goal_years))
        self.term_life_cover = float(term_life_cover)
        self.annual_income = float(annual_income)
        self.emi_total = float(emi_total)

    def generate(self) -> List[Dict[str, str]]:
        insights: List[Dict[str, str]] = []
        insights.extend(self._cash_drag_rule())
        insights.extend(self._risk_mismatch_rule())
        insights.extend(self._fd_overconcentration_rule())
        insights.extend(self._gold_overallocation_rule())
        insights.extend(self._insurance_adequacy_rule())
        insights.extend(self._emi_deduction_rule())
        if not insights:
            insights.append(
                {
                    "severity": "low",
                    "icon": "OK",
                    "message": (
                        "Your existing portfolio does not show any major concentration or "
                        "deployment issues under the current rules."
                    ),
                }
            )
        return insights

    def _cash_drag_rule(self) -> List[Dict[str, str]]:
        if self.total_corpus <= 0:
            return []
        cash_pct = float(self.asset_allocation.get("Savings / Cash", 0.0))
        cash_amount = self.total_corpus * cash_pct / 100.0
        threshold_pct = (3 * self.monthly_income / self.total_corpus) * 100.0 if self.monthly_income > 0 else 0.0
        if self.monthly_income > 0 and cash_pct > threshold_pct:
            excess_cash = max(0.0, cash_amount - (3 * self.monthly_income))
            return [
                {
                    "severity": "medium",
                    "icon": "WARN",
                    "message": (
                        f"Your ₹{cash_amount:,.0f} in savings/cash is earning ~3.5% "
                        f"(savings account rate) while inflation runs at ~{self.current_cpi:.1f}%. "
                        f"Consider moving ₹{excess_cash:,.0f} to liquid mutual funds for better post-tax returns."
                    ),
                }
            ]
        return []

    def _risk_mismatch_rule(self) -> List[Dict[str, str]]:
        equity_pct = float(self.asset_allocation.get("Mutual Funds / Equity", 0.0))
        if self.risk_score >= 7.5 and equity_pct < 30.0 and self.total_corpus > 0:
            target_equity_pct = max(30.0, float(risk_score_to_allocation(self.risk_score)["equity"]))
            current_equity_corpus = self.total_corpus * equity_pct / 100.0
            target_equity_corpus = self.total_corpus * target_equity_pct / 100.0
            equity_gap = max(0.0, target_equity_corpus - current_equity_corpus)
            estimated_opportunity_cost = equity_gap * ((1.12) ** self.goal_years)
            return [
                {
                    "severity": "high",
                    "icon": "CRIT",
                    "message": (
                        f"Your risk profile is Aggressive ({self.risk_score:.1f}/10) but only "
                        f"{equity_pct:.1f}% of your portfolio is in equity. This mismatch may cost "
                        f"you ₹{estimated_opportunity_cost:,.0f} over {self.goal_years} years."
                    ),
                }
            ]
        return []

    def _fd_overconcentration_rule(self) -> List[Dict[str, str]]:
        fd_pct = float(self.asset_allocation.get("Fixed Deposits / Bonds", 0.0))
        if fd_pct > 60.0:
            return [
                {
                    "severity": "medium",
                    "icon": "WARN",
                    "message": (
                        "Fixed Deposits above 60% concentration are tax-inefficient above the "
                        "₹40,000 TDS threshold. Debt mutual funds (IDCW option) may offer better "
                        "post-tax returns at your income level."
                    ),
                }
            ]
        return []

    def _gold_overallocation_rule(self) -> List[Dict[str, str]]:
        gold_pct = float(self.asset_allocation.get("Gold", 0.0))
        if gold_pct > 15.0:
            return [
                {
                    "severity": "low",
                    "icon": "INFO",
                    "message": (
                        f"Gold above 15% is considered non-yielding drag in long-term wealth "
                        f"building. Current allocation: {gold_pct:.1f}%. Consider capping at "
                        "10–15% as a hedge."
                    ),
                }
            ]
        return []

    def _insurance_adequacy_rule(self) -> List[Dict[str, str]]:
        recommended_cover = self.annual_income * 10.0
        if recommended_cover > 0 and self.term_life_cover < recommended_cover:
            return [
                {
                    "severity": "high",
                    "icon": "COVER",
                    "message": (
                        f"Your life cover (₹{self.term_life_cover:,.0f}) is below the "
                        f"recommended ₹{recommended_cover:,.0f}. Consider increasing term cover."
                    ),
                }
            ]
        return []

    def _emi_deduction_rule(self) -> List[Dict[str, str]]:
        if self.emi_total > 0:
            return [
                {
                    "severity": "medium",
                    "icon": "EMI",
                    "message": f"₹{self.emi_total:,.0f}/month EMI deducted from savings capacity.",
                }
            ]
        return []

def analyze_portfolio(
    existing_fd: float,
    existing_savings: float,
    existing_gold: float,
    existing_mutual_funds: float,
    risk_score: float = 5.0,
    monthly_income: float = 0.0,
    current_cpi: float = 6.0,
    goal_years: int = 10,
    term_life_cover: float = 0.0,
    outstanding_loans: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    Analyzes the existing asset distribution, computes risk alignment,
    quantifies cash drag, and generates dynamic insights.
    """
    total_corpus = (
        existing_fd + existing_savings + existing_gold + existing_mutual_funds
    )
    outstanding_loans = outstanding_loans or []
    total_liabilities = sum(
        float(loan.get("outstanding_principal", 0.0)) for loan in outstanding_loans
    )
    total_emi = sum(float(loan.get("emi", 0.0)) for loan in outstanding_loans)
    net_worth = total_corpus - total_liabilities

    if total_corpus == 0:
        return {
            "total_corpus": 0.0,
            "net_worth": round(net_worth, 2),
            "total_liabilities": round(total_liabilities, 2),
            "emi_total": round(total_emi, 2),
            "diversification_score": 0,
            "risk_exposure": "N/A (No Investments)",
            "insights": ["Start investing to build a portfolio. You currently have no deployed assets."],
            "prioritized_insights": [
                {
                    "severity": "medium",
                    "icon": "WARN",
                    "message": "Start investing to build a portfolio. You currently have no deployed assets.",
                }
            ],
            "breakdown": {},
        }

    breakdown = {
        "Fixed Deposits / Bonds": round((existing_fd / total_corpus) * 100, 2),
        "Savings / Cash": round((existing_savings / total_corpus) * 100, 2),
        "Gold": round((existing_gold / total_corpus) * 100, 2),
        "Mutual Funds / Equity": round((existing_mutual_funds / total_corpus) * 100, 2),
    }

    score = 10

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

    if risk_score <= 4.0 and actual_risk_val >= 9:
        # Conservative capacity, but behaving aggressively
        score -= 3
    elif breakdown["Mutual Funds / Equity"] < 20:
        score -= 1

    prioritized_insights = PortfolioInsightEngine(
        asset_allocation=breakdown,
        total_corpus=total_corpus,
        monthly_income=monthly_income,
        risk_score=risk_score,
        current_cpi=current_cpi,
        goal_years=goal_years,
        term_life_cover=term_life_cover,
        annual_income=monthly_income * 12.0,
        emi_total=total_emi,
    ).generate()

    severity_penalty = {"high": 3, "medium": 2, "low": 1}
    score -= sum(severity_penalty.get(insight["severity"], 0) for insight in prioritized_insights)
    insights = [insight["message"] for insight in prioritized_insights]

    return {
        "total_corpus": total_corpus,
        "net_worth": round(net_worth, 2),
        "total_liabilities": round(total_liabilities, 2),
        "emi_total": round(total_emi, 2),
        "diversification_score": max(0, score),
        "risk_exposure": f"{actual_risk} ({equity_exposure}% Equity)",
        "insights": insights,
        "prioritized_insights": prioritized_insights,
        "breakdown": breakdown,
    }
