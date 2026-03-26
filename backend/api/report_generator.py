from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class ReportGenerator:
    def __init__(self):
        self.report_data = {}

    def add_section(self, section_name: str, data: Dict[str, Any]) -> None:
        self.report_data[section_name] = {
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

    def add_risk_profile(self, risk_result: Dict[str, Any]) -> None:
        self.add_section("risk_profile", risk_result)

    def add_goals(self, goals: List[Dict[str, Any]]) -> None:
        self.add_section("goals", goals)

    def add_allocation(self, allocation: Dict[str, Any]) -> None:
        self.add_section("allocation", allocation)

    def add_portfolio(self, portfolio: Dict[str, Any]) -> None:
        self.add_section("portfolio", portfolio)

    def add_monte_carlo(self, monte_carlo: Dict[str, Any]) -> None:
        self.add_section("monte_carlo", monte_carlo)

    def add_macro_context(self, macro: Dict[str, Any]) -> None:
        self.add_section("macro_context", macro)

    def add_fund_intelligence(self, intelligence: Dict[str, Any]) -> None:
        self.add_section("fund_intelligence", intelligence)

    def generate_summary(self) -> Dict[str, Any]:
        summary = {
            "generated_at": datetime.now().isoformat(),
            "sections": list(self.report_data.keys()),
        }

        if "risk_profile" in self.report_data:
            risk = self.report_data["risk_profile"].get("data", {})
            summary["risk_score"] = risk.get("score")
            summary["risk_category"] = risk.get("category")

        if "goals" in self.report_data:
            goals = self.report_data["goals"].get("data", [])
            summary["total_goals"] = len(goals)
            summary["total_required_corpus"] = sum(
                g.get("future_corpus", 0) for g in goals
            )

        if "monte_carlo" in self.report_data:
            mc = self.report_data["monte_carlo"].get("data", {})
            summary["success_probability"] = mc.get("success_probability")

        return summary

    def to_dict(self) -> Dict[str, Any]:
        return {"report": self.report_data, "summary": self.generate_summary()}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AdvisorOverrideAPI:
    def __init__(self):
        self.overrides = {}

    def create_override(
        self,
        override_id: str,
        override_type: str,
        original_value: Any,
        new_value: Any,
        reason: str,
        advisor_id: str,
        client_id: str,
    ) -> Dict[str, Any]:
        override_record = {
            "override_id": override_id,
            "override_type": override_type,
            "original_value": original_value,
            "new_value": new_value,
            "reason": reason,
            "advisor_id": advisor_id,
            "client_id": client_id,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
            "approved": False,
        }
        self.overrides[override_id] = override_record
        return override_record

    def approve_override(self, override_id: str) -> Dict[str, Any]:
        if override_id in self.overrides:
            self.overrides[override_id]["status"] = "approved"
            self.overrides[override_id]["approved"] = True
            self.overrides[override_id]["approved_at"] = datetime.now().isoformat()
            return self.overrides[override_id]
        return {"error": "Override not found"}

    def reject_override(
        self, override_id: str, rejection_reason: str = ""
    ) -> Dict[str, Any]:
        if override_id in self.overrides:
            self.overrides[override_id]["status"] = "rejected"
            self.overrides[override_id]["rejection_reason"] = rejection_reason
            self.overrides[override_id]["rejected_at"] = datetime.now().isoformat()
            return self.overrides[override_id]
        return {"error": "Override not found"}

    def get_override(self, override_id: str) -> Optional[Dict[str, Any]]:
        return self.overrides.get(override_id)

    def get_client_overrides(self, client_id: str) -> List[Dict[str, Any]]:
        return [o for o in self.overrides.values() if o.get("client_id") == client_id]

    def get_pending_overrides(self) -> List[Dict[str, Any]]:
        return [o for o in self.overrides.values() if o.get("status") == "pending"]


class AIScoringEngine:
    def __init__(self):
        self.weights = {
            "risk_score": 0.25,
            "goal_alignment": 0.20,
            "diversification": 0.15,
            "performance": 0.20,
            "cost": 0.10,
            "consistency": 0.10,
        }

    def calculate_fund_score(
        self,
        fund_data: Dict[str, Any],
        client_profile: Dict[str, Any],
        market_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        scores = {}

        risk_score = client_profile.get("risk_score", 5)
        fund_risk = fund_data.get("risk_level", 3)
        scores["risk_alignment"] = 10 - abs(risk_score - fund_risk) * 2

        scores["goal_alignment"] = self._calculate_goal_alignment(
            fund_data, client_profile
        )

        scores["diversification"] = fund_data.get("diversification_score", 7)

        scores["performance"] = self._calculate_performance_score(
            fund_data, market_data
        )

        scores["cost"] = max(0, 10 - (fund_data.get("expense_ratio", 1.0) * 100))

        scores["consistency"] = fund_data.get("consistency_score", 7)

        weighted_score = sum(scores[key] * self.weights[key] for key in self.weights)

        final_score = round(weighted_score, 2)

        return {
            "final_score": final_score,
            "component_scores": {k: round(v, 2) for k, v in scores.items()},
            "rating": self._get_rating(final_score),
            "recommendation": self._get_recommendation(final_score),
        }

    def _calculate_goal_alignment(
        self, fund_data: Dict[str, Any], client_profile: Dict[str, Any]
    ) -> float:
        goal_type = client_profile.get("primary_goal", "wealth_creation")
        fund_category = fund_data.get("category", "")

        goal_category_map = {
            "retirement": ["Large Cap", "Index", "Multi Cap"],
            "child_education": ["Large Cap", "Mid Cap", "Multi Cap"],
            "house_purchase": ["Debt", "Hybrid", "Large Cap"],
            "wealth_creation": ["Large Cap", "Mid Cap", "Small Cap", "Multi Cap"],
            "income_generation": ["Debt", "Hybrid", "Liquid"],
        }

        aligned_categories = goal_category_map.get(goal_type, [])
        return 10.0 if fund_category in aligned_categories else 5.0

    def _calculate_performance_score(
        self, fund_data: Dict[str, Any], market_data: Dict[str, Any] = None
    ) -> float:
        returns = fund_data.get("returns", {})
        score = 7.0

        if returns.get("1y", 0) > 15:
            score += 2
        elif returns.get("1y", 0) < 0:
            score -= 3

        if returns.get("3y", 0) > 12:
            score += 1
        elif returns.get("3y", 0) < 0:
            score -= 2

        return min(10, max(0, score))

    def _get_rating(self, score: float) -> str:
        if score >= 8.5:
            return "Excellent"
        elif score >= 7.0:
            return "Good"
        elif score >= 5.5:
            return "Average"
        elif score >= 4.0:
            return "Below Average"
        else:
            return "Poor"

    def _get_recommendation(self, score: float) -> str:
        if score >= 8.0:
            return "Highly Recommended"
        elif score >= 6.5:
            return "Recommended"
        elif score >= 5.0:
            return "Consider with Caution"
        else:
            return "Not Recommended"


class MacroEngine:
    def __init__(self):
        self.current_context = None

    def update_context(
        self,
        inflation: float = None,
        interest_rate: float = None,
        market_volatility: float = None,
        geopolitical_risk: float = None,
    ) -> Dict[str, Any]:
        from backend.engines.intelligence.context_engine import get_macro_context

        self.current_context = get_macro_context(
            inflation_rate=inflation,
            interest_rate=interest_rate,
            market_volatility=market_volatility,
            geopolitical_risk=geopolitical_risk,
        )
        return self.current_context

    def get_current_context(self) -> Dict[str, Any]:
        if self.current_context is None:
            return self.update_context()
        return self.current_context

    def get_allocation_adjustments(
        self, base_allocation: Dict[str, float]
    ) -> Dict[str, Any]:
        context = self.get_current_context()
        adjustments = {}

        macro_score = context.get("macro_context_score", 0.5)
        volatility = context.get("market_volatility", 0.5)

        if macro_score < 0.4:
            adjustments["equity"] = -10
            adjustments["debt"] = 10
            adjustments["gold"] = 5
            adjustments["reason"] = (
                "Defensive macro environment - reducing equity exposure"
            )
        elif macro_score > 0.7 and volatility < 0.4:
            adjustments["equity"] = 10
            adjustments["debt"] = -5
            adjustments["gold"] = -5
            adjustments["reason"] = (
                "Favourable macro environment - increasing equity exposure"
            )
        else:
            adjustments["reason"] = (
                "Macro environment stable - maintaining current allocation"
            )

        adjusted = {}
        for asset, weight in base_allocation.items():
            adjustment = adjustments.get(asset.lower(), 0)
            adjusted[asset] = max(0, min(100, weight + adjustment))

        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: round((v / total) * 100, 2) for k, v in adjusted.items()}

        return {
            "original_allocation": base_allocation,
            "adjusted_allocation": adjusted,
            "adjustments": adjustments,
            "macro_context": context,
        }


def generate_complete_report(
    client_data: Dict[str, Any],
    risk_result: Dict[str, Any],
    goals: List[Dict[str, Any]],
    allocation: List[Dict[str, Any]],
    portfolio: List[Dict[str, Any]],
    monte_carlo_result: Dict[str, Any],
    fund_scores: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    generator = ReportGenerator()

    generator.add_risk_profile(risk_result)
    generator.add_goals(goals)
    generator.add_allocation({"funds": allocation})
    generator.add_portfolio({"holdings": portfolio})
    generator.add_monte_carlo(monte_carlo_result)

    macro_engine = MacroEngine()
    macro_context = macro_engine.get_current_context()
    generator.add_macro_context(macro_context)

    fund_intel = {
        "scored_funds": fund_scores or [],
        "top_recommendations": fund_scores[:5] if fund_scores else [],
    }
    generator.add_fund_intelligence(fund_intel)

    return generator.to_dict()


try:
    from flask import Blueprint, request, jsonify

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Blueprint = None

if FLASK_AVAILABLE:
    report_bp = Blueprint("report", __name__)

    @report_bp.route("/generate-report", methods=["POST"])
    def generate_report_endpoint():
        data = request.json
        profile = data.get("profile", {})

        try:
            from backend.engines.risk_engine import calculate_risk_score

            risk = calculate_risk_score(
                profile.get("age", 30),
                profile.get("dependents", 0),
                profile.get("income", 100000),
                profile.get("savings", 10000),
                profile.get("behavior", "moderate"),
            )
        except Exception as e:
            risk = {"score": 5.0, "category": "Moderate", "error": str(e)}

        try:
            from backend.intelligence.macro_engine import calculate_macro_stability

            macro = calculate_macro_stability(
                data.get("cpi", 5.5),
                data.get("vix", 15),
                data.get("geopolitical_level", "medium"),
            )
        except Exception as e:
            macro = {"stability_score": 0.7, "label": "NEUTRAL", "error": str(e)}

        goals = []
        for g in data.get("goals", []):
            try:
                from backend.goals.goal_registry import GoalRegistry

                goal_result = GoalRegistry.calculate_required_corpus(
                    g.get("type", "wealth_creation"),
                    g.get("inputs", {}),
                    g.get("return_pct", 11.0),
                )
                goals.append(goal_result)
            except Exception as e:
                goals.append({"error": str(e)})

        funds = data.get("funds", [])
        for f in funds:
            try:
                from backend.funds.ai_scorer import calculate_ai_score

                ai_result = calculate_ai_score(f, macro.get("market_signal", "NEUTRAL"))
                f["ai_score"] = ai_result["ai_score"]
                f["ai_breakdown"] = ai_result["components"]
            except Exception as e:
                f["ai_score"] = 5.0

        try:
            from backend.funds.overlap_engine import eliminate_overlapping_funds

            funds = eliminate_overlapping_funds(funds)
        except Exception:
            pass

        try:
            from backend.funds.investment_mode import (
                determine_market_regime,
                recommend_mode,
            )

            regime = determine_market_regime(data.get("market_signals", {}))
            for f in funds:
                mode_result = recommend_mode(f, regime, profile.get("savings", 10000))
                f["recommended_mode"] = mode_result
        except Exception:
            pass

        try:
            from backend.insurance.gap_analyzer import analyze_insurance_gap

            insurance = analyze_insurance_gap(
                profile, data.get("existing_insurance", {})
            )
        except Exception as e:
            insurance = {"error": str(e)}

        return jsonify(
            {
                "status": "success",
                "risk": risk,
                "macro": macro,
                "goals": goals,
                "funds": funds,
                "insurance": insurance,
            }
        )


if __name__ == "__main__":
    test_risk = {"score": 6.5, "category": "Moderate"}
    test_goals = [
        {"goal_name": "Retirement", "future_corpus": 5000000, "required_sip": 25000}
    ]
    test_allocation = [
        {"fund_name": "HDFC Top 100", "category": "Large Cap", "weight": 30}
    ]
    test_portfolio = []
    test_mc = {"success_probability": 78.5}

    report = generate_complete_report(
        {"name": "Test Client"},
        test_risk,
        test_goals,
        test_allocation,
        test_portfolio,
        test_mc,
    )
    print(json.dumps(report, indent=2))


def generate_report_v2_data(client_data: Dict[str, Any], analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synthesizes all raw engine outputs into the structured format required by the V2 PDF template.
    """
    from backend.insurance.gap_analyzer import generate_insurance_recommendations, calculate_health_insurance_gap, analyze_insurance_gap
    from backend.funds.investment_mode import get_recommended_strategy
    
    # 1. Profile & Basic Data
    profile = {
        "age": client_data.get("age", 30),
        "dependents": client_data.get("dependents", 0),
        "monthly_income": client_data.get("monthly_income", 100000),
        "monthly_savings": client_data.get("monthly_savings", 20000),
        "behavior": client_data.get("behavior", "Moderate"),
        "total_liabilities": client_data.get("total_liabilities", 0)
    }

    # 2. Risk Profile
    risk_raw = analysis_data.get("risk", {})
    risk = {
        "score": risk_raw.get("score", 5.0),
        "category": risk_raw.get("category", "Moderate"),
        "explanation": risk_raw.get("explanation", {
            "Age": 2.0, "Dependents": -0.5, "Income": 1.5, "Behavior": 2.0
        })
    }

    # 3. Goals
    goals_raw = analysis_data.get("goals", [])
    goals = []
    for g in goals_raw:
        goals.append({
            "name": g.get("name", "Goal"),
            "years": g.get("years_to_goal", 10),
            "future_value": g.get("future_corpus", 0),
            "roi": g.get("return_pct", 12.0),
            "inflation": g.get("inflation_rate", 6.0),
            "required_sip": g.get("required_sip", 0),
            "step_up": 10 if g.get("future_corpus", 0) > 1000000 else 5,
            "annuity": g.get("future_corpus", 0) * 0.005 # Mock annuity rule
        })

    # 4. Insurance & Liabilities
    existing_ins = client_data.get("existing_insurance", {})
    insurance = {
        "life_cover": existing_ins.get("term", 0),
        "life_gap": analyze_insurance_gap(profile, existing_ins).get("term_gap", 0),
        "health_cover": existing_ins.get("health", 0),
        "health_gap": calculate_health_insurance_gap(profile, existing_ins).get("gap", 0),
        "recommendations": generate_insurance_recommendations(profile, existing_ins)
    }

    # 5. Portfolio Health & Insights
    portfolio_raw = analysis_data.get("portfolio", {})
    div_score = portfolio_raw.get("diversification_score", 7.0)
    
    # Generate dynamic insights v2
    insights_v2 = []
    if div_score < 8.0:
        insights_v2.append({"type": "warning", "headline": "Diversification Trap", "text": "High concentration in single-cap funds identified."})
    else:
        insights_v2.append({"type": "success", "headline": "Well Balanced", "text": "Portfolio effectively covers Equity, Debt, and Gold."})
    
    if profile["monthly_savings"] < goals[0]["required_sip"] if goals else False:
        insights_v2.append({"type": "danger", "headline": "Savings Shortfall", "text": "Current savings capacity is 30% below required levels for primary goals."})

    portfolio = {
        "total_corpus": portfolio_raw.get("total_corpus", 0.0),
        "diversification_score": div_score,
        "insights_v2": insights_v2
    }

    # 6. Allocation & Macro
    macro_raw = analysis_data.get("macro", {})
    macro = {
        "stability": macro_raw.get("stability_score", 0.8) * 100,
        "ai_market_score": macro_raw.get("ai_market_score", 85)
    }
    
    allocation = {
        "targets": [
            {"name": "Large Cap Equity", "percent": 40, "rationale": "Core stability and benchmark tracking."},
            {"name": "Mid/Small Cap", "percent": 30, "rationale": "Alpha generation for long-horizon goals."},
            {"name": "Debt / Fixed Income", "percent": 20, "rationale": "Capital preservation and volatility dampening."},
            {"name": "Gold / Alt", "percent": 10, "rationale": "Hedge against systemic macro shocks."}
        ]
    }

    # 7. Investment Mode
    mode_raw = get_recommended_strategy(profile, {"vix": 18, "nifty_signal": "neutral"})
    investment_mode = {
        "title": mode_raw.get("primary_mode", "SIP"),
        "description": mode_raw.get("rationale", "Systematic entry recommended.")
    }

    # 8. Funds
    funds_raw = analysis_data.get("funds", [])
    funds = []
    for f in funds_raw:
        funds.append({
            "name": f.get("name", "Unknown Fund"),
            "ai_reason": f.get("ai_reason", "High persistence in risk-adjusted returns."),
            "alpha": f.get("alpha", 2.1),
            "weight": f.get("weight", 20),
            "score": f.get("ai_score", 85)
        })

    # 9. Scenarios & Projections
    scenarios = {
        "base_roi": 12.0,
        "step_up_pct": 10,
        "inflation_rate": 6.0,
        "inflation_adjusted": True,
        "projections": [
            {"year": 5, "base_val": profile["monthly_savings"] * 70, "step_val": profile["monthly_savings"] * 85},
            {"year": 10, "base_val": profile["monthly_savings"] * 180, "step_val": profile["monthly_savings"] * 240},
            {"year": 20, "base_val": profile["monthly_savings"] * 600, "step_val": profile["monthly_savings"] * 950}
        ]
    }

    # 10. Monte Carlo
    mc_raw = analysis_data.get("monte_carlo", {})
    prob = mc_raw.get("success_probability", 75.0)
    monte_carlo = {
        "prob": prob,
        "interpretation": "Strong likelihood of success under normal conditions." if prob >= 80 else "Requires intervention to improve probability.",
        "fix_recommendation": "Consider increasing SIP by 15% or extending goal by 2 years."
    }

    return {
        "client": profile,
        "risk": risk,
        "goals": goals,
        "insurance": insurance,
        "portfolio": portfolio,
        "macro": macro,
        "allocation": allocation,
        "investment_mode": investment_mode,
        "funds": funds,
        "scenarios": scenarios,
        "monte_carlo": monte_carlo
    }


def generate_full_report(client_data, analysis_data):
    # This is the old version, keeping it for compatibility but mapping to V2 data structure
    v2_data = generate_report_v2_data(client_data, analysis_data)
    from backend.report.pdf_generator import generate_financial_report
    
    # Trigger the PDF generation
    output_path = generate_financial_report(
        client_data=v2_data["client"],
        risk_data=v2_data["risk"],
        goals=v2_data["goals"],
        allocation_data=v2_data["allocation"],
        portfolio_data=v2_data["portfolio"],
        insurance_data=v2_data["insurance"],
        macro_data=v2_data["macro"],
        funds=v2_data["funds"],
        monte_carlo=v2_data["monte_carlo"],
        scenarios=v2_data["scenarios"],
        investment_mode=v2_data["investment_mode"]
    )
    
    return {"status": "success", "pdf_path": output_path, "data": v2_data}
