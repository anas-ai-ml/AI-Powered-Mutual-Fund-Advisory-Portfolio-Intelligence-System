from typing import Dict, Any, List, Optional
from datetime import datetime
import json


def _extract_macro_value(value: Any, default: float = 0.0) -> float:
    if isinstance(value, dict):
        return float(value.get("value", default) or default)
    if value is None:
        return float(default)
    return float(value)


def _extract_macro_source(value: Any, default: str = "Fallback macro context") -> str:
    if isinstance(value, dict):
        return str(value.get("source") or default)
    return default


def _extract_macro_time(value: Any, default: Optional[str] = None) -> Optional[str]:
    if isinstance(value, dict):
        return value.get("fetched_at") or default
    return default


def _format_as_of(value: Optional[str]) -> str:
    if not value:
        return datetime.now().strftime("%d %b %Y, %I:%M %p")
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %I:%M %p")
    except ValueError:
        return str(value)


def _safe_pct(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric * 100.0 if abs(numeric) <= 1.0 else numeric


def _severity_to_class(severity: str) -> str:
    mapping = {"high": "danger", "medium": "warning", "low": "success"}
    return mapping.get(str(severity).lower(), "warning")


def _source_row(source: str, as_of: Optional[str]) -> str:
    return f"Source: {source} | As of {_format_as_of(as_of)}"


def _extract_retirement_age(client_data: Dict[str, Any], default: int = 60) -> int:
    raw_goals = client_data.get("goals", [])
    if isinstance(raw_goals, list):
        for goal in raw_goals:
            if not isinstance(goal, dict):
                continue
            goal_type = str(goal.get("type") or goal.get("goal_type") or "").strip().lower()
            if goal_type == "retirement":
                inputs = goal.get("inputs") or {}
                try:
                    return int(inputs.get("retirement_age", default))
                except (TypeError, ValueError):
                    return default
    if isinstance(raw_goals, dict):
        retirement_goal = raw_goals.get("retirement", {})
        try:
            return int(
                retirement_goal.get(
                    "retirement_age",
                    client_data.get("target_retirement_age", default),
                )
            )
        except (TypeError, ValueError):
            return default
    try:
        return int(client_data.get("target_retirement_age", default))
    except (TypeError, ValueError):
        return default


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
    from backend.engines.explanation_standards import get_score_reasoning
    from backend.engines.projection_engine import generate_projection_table
    from backend.insurance.gap_analyzer import (
        analyze_insurance_gap,
        calculate_health_insurance_gap,
        generate_insurance_recommendations,
    )
    from backend.processors.explainability import explain_all_funds
    from backend.processors.output_formatter import build_projection_assumptions
    from backend.scoring.monte_carlo_remediation import (
        build_sensitivity_analysis,
        generate_fix_recommendation,
    )

    today = datetime.now().strftime("%d %b %Y")
    now_iso = datetime.now().isoformat()

    insurance_inputs = client_data.get("insurance_inputs", {})
    outstanding_loans = insurance_inputs.get("outstanding_loans", [])
    existing_ins = client_data.get("existing_insurance", {})
    macro_raw = analysis_data.get("macro", {})
    inflation_meta = macro_raw.get("inflation", {})
    policy_meta = macro_raw.get("policy_rate", macro_raw.get("repo_rate", {}))
    macro_source = macro_raw.get("source", "fallback")
    macro_as_of = _extract_macro_time(inflation_meta, macro_raw.get("fetched_at", now_iso))

    # 1. Profile & Basic Data
    profile = {
        "age": client_data.get("age", 30),
        "dependents": client_data.get("dependents", 0),
        "monthly_income": client_data.get("monthly_income", 100000),
        "monthly_savings": client_data.get("monthly_savings", 20000),
        "effective_monthly_savings": client_data.get(
            "effective_monthly_savings", client_data.get("monthly_savings", 20000)
        ),
        "behavior": client_data.get("behavior", "Moderate"),
        "existing_corpus": float(client_data.get("existing_corpus", 0.0)),
        "total_liabilities": client_data.get("total_liabilities", 0),
        "term_life_cover": float(insurance_inputs.get("term_life_cover", 0.0)),
        "health_cover": float(insurance_inputs.get("health_cover", 0.0)),
        "annual_insurance_premium": float(
            insurance_inputs.get("annual_insurance_premium", 0.0)
        ),
        "emi_total": float(client_data.get("emi_total", 0.0)),
        "source_note": _source_row("Client declaration", now_iso),
    }

    # 2. Risk Profile
    risk_raw = analysis_data.get("risk", {})
    risk_standard = get_score_reasoning("Risk Score")
    risk_explanation = risk_raw.get("explanation") or risk_raw.get("feature_contributions") or {
        "Age": 2.0,
        "Dependents": -0.5,
        "Income": 1.5,
        "Behavior": 2.0,
    }
    risk = {
        "score": risk_raw.get("score", 5.0),
        "category": risk_raw.get("category", "Moderate"),
        "explanation": risk_explanation,
        "methodology_note": risk_standard.user_facing_summary,
        "mathematical_basis": risk_standard.mathematical_basis,
        "source_note": _source_row("Risk Engine + client profile", now_iso),
    }

    # 3. Goals
    goals_raw = analysis_data.get("goals", [])
    goals = []
    primary_goal = goals_raw[0] if goals_raw else {}
    inflation_rate = _extract_macro_value(inflation_meta, 0.06)
    inflation_source = _extract_macro_source(inflation_meta, "Fallback macro context")
    base_roi = float(
        primary_goal.get("expected_return_rate", client_data.get("projection_base_roi", 0.12))
        or 0.12
    )
    topup_rate = float(
        primary_goal.get(
            "annual_sip_step_up",
            client_data.get("annual_sip_step_up_pct", 10.0) / 100.0,
        )
        or 0.0
    )
    for g in goals_raw:
        sip_comparison = g.get("sip_comparison", {})
        roi_value = float(g.get("expected_return_rate", g.get("return_pct", base_roi)))
        inflation_value = float(g.get("inflation_rate", inflation_rate))
        goal_name = g.get("goal_name", g.get("name", "Goal"))
        assumptions = build_projection_assumptions(
            inflation_rate=inflation_value,
            inflation_source=inflation_source,
            roi=roi_value,
            roi_basis=f"{goal_name} projection base-case assumption",
            sip_topup_rate=float(g.get("annual_sip_step_up", topup_rate)),
        )
        distribution_phase = g.get("distribution_phase", {})
        goals.append({
            "name": goal_name,
            "years": g.get("years_to_goal", 10),
            "future_value": g.get("future_corpus", 0),
            "roi": round(roi_value * 100 if roi_value <= 1 else roi_value, 2),
            "inflation": round(
                inflation_value * 100 if inflation_value <= 1 else inflation_value, 2
            ),
            "required_sip": g.get("required_sip", 0),
            "step_up": sip_comparison.get(
                "annual_step_up_pct",
                float(g.get("annual_sip_step_up", topup_rate)) * 100,
            ),
            "sip_comparison": sip_comparison,
            "annuity": distribution_phase.get("annuity_corpus_required", 0.0),
            "distribution_phase": distribution_phase,
            "assumptions": assumptions,
            "source_note": _source_row(
                f"{goal_name} planning engine",
                macro_as_of,
            ),
        })

    # 4. Insurance & Liabilities
    total_liabilities = sum(
        float(loan.get("outstanding_principal", 0.0)) for loan in outstanding_loans
    )
    total_emi = sum(float(loan.get("emi", 0.0)) for loan in outstanding_loans)
    recommended_term_cover = float(profile.get("monthly_income", 0.0)) * 12.0 * 10.0
    insurance_gap = analyze_insurance_gap(profile, existing_ins)
    insurance = {
        "life_cover": insurance_inputs.get("term_life_cover", existing_ins.get("term", 0)),
        "life_gap": insurance_gap.get("term_gap", 0),
        "health_cover": insurance_inputs.get("health_cover", existing_ins.get("health", 0)),
        "health_gap": calculate_health_insurance_gap(profile, existing_ins).get("gap", 0),
        "annual_insurance_premium": insurance_inputs.get("annual_insurance_premium", 0.0),
        "recommended_term_cover": recommended_term_cover,
        "total_liabilities": total_liabilities,
        "total_emi": total_emi,
        "loans": outstanding_loans,
        "recommendations": generate_insurance_recommendations(profile, existing_ins),
        "source_note": _source_row("Insurance inputs + liability schedule", now_iso),
    }

    # 5. Portfolio Health & Insights
    portfolio_raw = analysis_data.get("portfolio", {})
    div_score = float(portfolio_raw.get("diversification_score", 7.0))
    prioritized_insights = portfolio_raw.get("prioritized_insights", [])
    if not prioritized_insights and portfolio_raw.get("insights", []):
        prioritized_insights = [
            {"severity": "medium", "icon": "WARN", "message": message}
            for message in portfolio_raw.get("insights", [])
        ]
    insight_cards = []
    for insight in prioritized_insights:
        severity = str(insight.get("severity", "medium")).lower()
        icon = insight.get("icon", "")
        message = insight.get("message", "")
        headline = {
            "high": "Action Required",
            "medium": "Attention",
            "low": "On Track",
        }.get(severity, "Attention")
        insight_cards.append(
            {
                "type": _severity_to_class(severity),
                "severity": severity,
                "headline": f"{icon} {headline}".strip(),
                "text": message,
            }
        )
    portfolio = {
        "total_corpus": portfolio_raw.get("total_corpus", 0.0),
        "net_worth": portfolio_raw.get(
            "net_worth", portfolio_raw.get("total_corpus", 0.0) - total_liabilities
        ),
        "total_liabilities": portfolio_raw.get("total_liabilities", total_liabilities),
        "diversification_score": div_score,
        "risk_exposure": portfolio_raw.get("risk_exposure", "Not available"),
        "breakdown": portfolio_raw.get("breakdown", {}),
        "insights_v2": insight_cards,
        "source_note": _source_row("Portfolio Health Engine", macro_as_of),
    }

    # 6. Portfolio Rebalancing Action Plan
    rebalancing_raw = analysis_data.get("portfolio_rebalancing", {})
    rebalancing_actions = []
    for item in rebalancing_raw.get("fund_actions", []):
        rebalancing_actions.append(
            {
                "action": str(item.get("action", "MAINTAIN")),
                "asset_class": str(item.get("asset_class", "")).title(),
                "fund_name": item.get("fund_name") or item.get("replaces") or "-",
                "monthly_sip": float(item.get("suggested_sip", 0.0) or 0.0),
                "lumpsum": float(item.get("suggested_lumpsum", 0.0) or 0.0),
                "urgency": str(item.get("urgency", "low")).title(),
            }
        )
    portfolio_rebalancing = {
        "actions": rebalancing_actions,
        "source_note": _source_row("Portfolio Gap Advisor", macro_as_of),
    }

    # 7. Allocation & Macro
    macro = {
        "stability": _safe_pct(
            macro_raw.get("market_stability_score", macro_raw.get("stability_score", 0.8)),
            80.0,
        ),
        "ai_market_score": float(
            macro_raw.get(
                "ai_market_score",
                sum(float(f.get("score", 0.0)) for f in analysis_data.get("funds", [])[:3]) / max(len(analysis_data.get("funds", [])[:3]), 1)
                if analysis_data.get("funds")
                else 85,
            )
        ),
        "inflation_rate": inflation_rate,
        "inflation_source": inflation_source,
        "policy_rate": _extract_macro_value(policy_meta, 6.5),
        "policy_source": _extract_macro_source(policy_meta, "RBI"),
        "source": macro_source,
        "as_of": _format_as_of(macro_as_of),
    }

    allocation_raw = analysis_data.get("allocation", {})
    allocation_map = allocation_raw.get("allocation", allocation_raw.get("adjusted_allocation", {}))
    if not allocation_map:
        allocation_map = {
            "Large Cap Equity": 40,
            "Mid/Small Cap": 30,
            "Debt / Fixed Income": 20,
            "Gold / Alt": 10,
        }
    allocation = {
        "targets": [
            {
                "name": asset,
                "percent": round(float(weight), 2),
                "rationale": (
                    "Core growth exposure."
                    if "equity" in asset.lower()
                    else "Capital preservation and volatility dampening."
                    if "debt" in asset.lower() or "bond" in asset.lower()
                    else "Macro hedge and diversification."
                ),
            }
            for asset, weight in allocation_map.items()
        ],
        "reasoning": (
            f"Based on Risk Score {risk['score']:.1f} and current Market Stability "
            f"{macro['stability']:.0f}%."
        ),
        "source_note": _source_row("Allocation Engine + macro overlay", macro_as_of),
    }

    # 8. Investment Mode
    mode_raw = analysis_data.get("investment_mode_recommendation") or analysis_data.get("investment_mode") or {}
    investment_mode = {
        "title": mode_raw.get("recommended_mode", mode_raw.get("primary_mode", "SIP")),
        "description": mode_raw.get("trigger_reason", mode_raw.get("rationale", "Systematic entry recommended.")),
        "trigger_reason": mode_raw.get("trigger_reason", "Market conditions favour phased deployment."),
        "deployment_plan": mode_raw.get("deployment_plan", "Deploy via SIP over the next 6-12 months."),
        "expected_advantage_vs_flat_sip": mode_raw.get(
            "expected_advantage_vs_flat_sip",
            "Designed to improve deployment timing versus a flat SIP path.",
        ),
        "source_note": _source_row("Investment Mode Engine", macro_as_of),
    }

    # 9. Funds
    funds_raw = analysis_data.get("funds", [])
    fund_explanations = {item["name"]: item for item in explain_all_funds(funds_raw)}
    funds = []
    for f in funds_raw:
        explanation = fund_explanations.get(f.get("name", ""), {})
        rationale = explanation.get("rationale", {})
        funds.append({
            "name": f.get("name", "Unknown Fund"),
            "category": f.get("category", "N/A"),
            "ai_reason": explanation.get("reason", f.get("reason", "High persistence in risk-adjusted returns.")),
            "weight": f.get("allocation_weight", f.get("weight", 20)),
            "score": f.get("score", f.get("ai_score", 85)),
            "benchmark_index": f.get("benchmark_index", "Benchmark"),
            "benchmark_1y_return": f.get("benchmark_1y_return", 0.0),
            "benchmark_3y_return": f.get("benchmark_3y_return", 0.0),
            "alpha_1y": f.get("alpha_1y", 0.0),
            "alpha_3y": f.get("alpha_3y", f.get("alpha", 0.0)),
            "information_ratio": f.get("information_ratio", 0.0),
            "why_selected": rationale.get("why_selected", ""),
            "why_now": rationale.get("why_now", ""),
            "risk_note": rationale.get("risk_note", ""),
        })

    # 10. Scenarios & Projections
    primary_goal_raw = primary_goal
    primary_sip_comparison = primary_goal_raw.get("sip_comparison", {})
    goal_years = int(primary_goal_raw.get("years_to_goal", 10) or 10)
    monthly_savings_capacity = float(
        client_data.get("effective_monthly_savings", client_data.get("monthly_savings", 0.0))
    )
    existing_corpus = float(client_data.get("existing_corpus", 0.0))
    timeline_df = generate_projection_table(
        initial_investment=existing_corpus,
        monthly_sip=monthly_savings_capacity,
        annual_return_rate=base_roi,
        years=goal_years,
    )
    timeline_rows = [
        {
            "year": int(row["year"]),
            "invested": float(row["invested"]),
            "projected_value": float(row["total_value"]),
            "wealth_created": float(row["returns"]),
        }
        for _, row in timeline_df.iterrows()
    ]
    scenario_rows = []
    for scenario_name, scenario_return in (
        ("Conservative", 0.08),
        ("Moderate", 0.12),
        ("Aggressive", 0.15),
    ):
        projection_df = generate_projection_table(
            initial_investment=existing_corpus,
            monthly_sip=monthly_savings_capacity,
            annual_return_rate=scenario_return,
            years=goal_years,
        )
        projected_corpus = float(projection_df.iloc[-1]["total_value"]) if not projection_df.empty else existing_corpus
        inflation_adjusted = projected_corpus / ((1 + inflation_rate) ** goal_years) if goal_years > 0 else projected_corpus
        probability = None
        if scenario_name == "Moderate":
            probability = analysis_data.get("monte_carlo", {}).get("success_probability")
        scenario_rows.append(
            {
                "scenario": scenario_name,
                "return_assumption": f"{scenario_return:.0%}",
                "final_corpus": round(projected_corpus, 2),
                "inflation_adjusted_corpus": round(inflation_adjusted, 2),
                "probability": probability,
            }
        )
    scenarios = {
        "assumptions": build_projection_assumptions(
            inflation_rate=inflation_rate,
            inflation_source=inflation_source,
            roi=base_roi,
            roi_basis="Goal horizon base-case assumption",
            sip_topup_rate=topup_rate,
        ),
        "base_roi": round(base_roi * 100, 2),
        "step_up_pct": primary_sip_comparison.get(
            "annual_step_up_pct",
            client_data.get("annual_sip_step_up_pct", 10.0),
        ),
        "inflation_rate": round(inflation_rate * 100, 2),
        "inflation_adjusted": True,
        "projections": timeline_rows,
        "goal_horizon": scenario_rows,
        "step_up_comparison": [
            primary_sip_comparison.get("flat", {}),
            primary_sip_comparison.get("step_up", {}),
        ],
        "step_up_note": primary_sip_comparison.get("note", ""),
        "source_note": _source_row("Projection Engine + macro assumptions", macro_as_of),
    }

    # 11. Monte Carlo
    mc_raw = analysis_data.get("monte_carlo", {})
    prob = float(mc_raw.get("success_probability", 75.0))
    required_sip = float(primary_goal_raw.get("required_sip", 0.0))
    fix_recommendation = None
    if primary_goal_raw and prob < 80:
        fix_recommendation = generate_fix_recommendation(
            current_sip=monthly_savings_capacity,
            required_sip=required_sip,
            required_corpus=float(primary_goal_raw.get("future_corpus", 0.0)),
            current_age=int(client_data.get("age", 30)),
            retirement_age=_extract_retirement_age(client_data, 60),
            current_monthly_expense=float(client_data.get("monthly_expense", 0.0)),
            existing_corpus=existing_corpus,
            expected_return=base_roi,
            gross_monthly_savings=float(client_data.get("monthly_savings", 0.0)),
            emi_total=float(client_data.get("emi_total", 0.0)),
        )
    sensitivity = None
    if primary_goal_raw and goal_years > 0 and required_sip > 0:
        sensitivity = build_sensitivity_analysis(
            current_sip=monthly_savings_capacity,
            required_sip=required_sip,
            initial_corpus=existing_corpus,
            target_corpus=float(primary_goal_raw.get("future_corpus", 0.0)),
            years=goal_years,
            expected_return=base_roi,
            annual_volatility=0.15,
            points=10,
        )
    monte_carlo = {
        "prob": prob,
        "interpretation": "Strong likelihood of success under normal conditions." if prob >= 80 else "Confidence is below institutional comfort levels and needs remediation.",
        "fix_recommendation": fix_recommendation,
        "sensitivity_analysis": sensitivity,
        "source_note": _source_row("Monte Carlo Engine (1,000 GBM paths)", macro_as_of),
    }

    score_dashboard = [
        {
            "label": "Risk",
            "value": f"{risk['score']:.1f}/10",
            "status": "On Track" if risk["score"] >= 7 else "Attention" if risk["score"] >= 5 else "Action Required",
            "icon": "✅" if risk["score"] >= 7 else "⚠️" if risk["score"] >= 5 else "❌",
        },
        {
            "label": "Diversification",
            "value": f"{portfolio['diversification_score']:.1f}/10",
            "status": "On Track" if portfolio["diversification_score"] >= 8 else "Attention" if portfolio["diversification_score"] >= 5 else "Action Required",
            "icon": "✅" if portfolio["diversification_score"] >= 8 else "⚠️" if portfolio["diversification_score"] >= 5 else "❌",
        },
        {
            "label": "AI Market",
            "value": f"{macro['ai_market_score']:.0f}/100",
            "status": "On Track" if macro["ai_market_score"] >= 80 else "Attention" if macro["ai_market_score"] >= 50 else "Action Required",
            "icon": "✅" if macro["ai_market_score"] >= 80 else "⚠️" if macro["ai_market_score"] >= 50 else "❌",
        },
        {
            "label": "Market Stability",
            "value": f"{macro['stability']:.0f}%",
            "status": "On Track" if macro["stability"] >= 80 else "Attention" if macro["stability"] >= 50 else "Action Required",
            "icon": "✅" if macro["stability"] >= 80 else "⚠️" if macro["stability"] >= 50 else "❌",
        },
        {
            "label": "Goal Confidence",
            "value": f"{monte_carlo['prob']:.0f}%",
            "status": "On Track" if monte_carlo["prob"] >= 80 else "Attention" if monte_carlo["prob"] >= 50 else "Action Required",
            "icon": "✅" if monte_carlo["prob"] >= 80 else "⚠️" if monte_carlo["prob"] >= 50 else "❌",
        },
    ]

    executive_summary = {
        "overview": (
            "This report combines client profile inputs, current macro conditions, "
            "goal projections, and portfolio diagnostics into one deployment-ready plan."
        ),
        "score_dashboard": score_dashboard,
        "data_freshness_note": analysis_data.get("data_freshness_note"),
        "source_note": _source_row("Integrated planning stack", now_iso),
    }

    return {
        "executive_summary": executive_summary,
        "client": profile,
        "risk": risk,
        "goals": goals,
        "insurance": insurance,
        "portfolio": portfolio,
        "portfolio_rebalancing": portfolio_rebalancing,
        "macro": macro,
        "allocation": allocation,
        "investment_mode": investment_mode,
        "funds": funds,
        "scenarios": scenarios,
        "monte_carlo": monte_carlo,
    }


def generate_full_report(client_data, analysis_data):
    # This is the old version, keeping it for compatibility but mapping to V2 data structure
    v2_data = generate_report_v2_data(client_data, analysis_data)
    from backend.report.pdf_generator import generate_financial_report
    
    # Trigger the PDF generation
    output_path = generate_financial_report(
        executive_summary=v2_data.get("executive_summary", {}),
        client_data=v2_data["client"],
        risk_data=v2_data["risk"],
        goals=v2_data["goals"],
        allocation_data=v2_data["allocation"],
        portfolio_data=v2_data["portfolio"],
        portfolio_rebalancing=v2_data["portfolio_rebalancing"],
        insurance_data=v2_data["insurance"],
        macro_data=v2_data["macro"],
        funds=v2_data["funds"],
        monte_carlo=v2_data["monte_carlo"],
        scenarios=v2_data["scenarios"],
        investment_mode=v2_data["investment_mode"]
    )

    with open(output_path, "rb") as pdf_file:
        return pdf_file.read()


def generate_proposal_deck_data(client_data: Dict[str, Any], analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    v2_data = generate_report_v2_data(client_data, analysis_data)
    client_name = str(
        client_data.get("name")
        or client_data.get("client_name")
        or client_data.get("marital_status", "Client")
    )
    monthly_sip = float(
        client_data.get(
            "effective_monthly_savings",
            client_data.get("monthly_savings", 0.0),
        )
    )
    base_roi = 0.12
    inflation_rate = float(v2_data.get("macro", {}).get("inflation_rate", 0.06))
    sip_rows = []
    for years in (10, 15, 20):
        months = years * 12
        projected_corpus = (
            monthly_sip
            * (((1 + (base_roi / 12.0)) ** months - 1) / (base_roi / 12.0))
            * (1 + (base_roi / 12.0))
            if monthly_sip > 0
            else 0.0
        )
        total_invested = monthly_sip * months
        multiplier = projected_corpus / total_invested if total_invested > 0 else 0.0
        sip_rows.append(
            {
                "horizon": f"{years} Years",
                "monthly_sip": monthly_sip,
                "total_invested": total_invested,
                "projected_corpus": projected_corpus,
                "multiplier": multiplier,
            }
        )

    funds = analysis_data.get("funds", [])
    historical_rows = [
        {
            "name": fund.get("name", "Unknown Fund"),
            "category": fund.get("category", "N/A"),
            "weight": float(fund.get("allocation_weight", fund.get("weight", 0.0))),
            "return_1y": float(fund.get("1y", 0.0)),
            "return_3y": float(fund.get("3y", 0.0)),
            "return_5y": float(fund.get("5y", 0.0)),
        }
        for fund in funds
    ]
    benchmark_rows = [
        {
            "name": fund.get("name", "Unknown Fund"),
            "benchmark_index": fund.get("benchmark_index", "Benchmark"),
            "benchmark_1y_return": float(fund.get("benchmark_1y_return", 0.0)),
            "benchmark_3y_return": float(fund.get("benchmark_3y_return", 0.0)),
            "alpha_1y": float(fund.get("alpha_1y", 0.0)),
            "alpha_3y": float(fund.get("alpha_3y", 0.0)),
        }
        for fund in funds
    ]

    allocation_reasoning = v2_data.get("allocation", {}).get("reasoning", "Recommended based on risk profile and market context.")
    investment_mode = v2_data.get("investment_mode", {})
    advisor_name = str(client_data.get("advisor_name") or "Assigned Advisor")
    advisor_email = str(client_data.get("advisor_email") or "advisor@example.com")
    advisor_role = str(client_data.get("advisor_role") or "Advisor")

    return {
        "title": f"{client_name} Investment Proposal",
        "subtitle": "A shareable advisor presentation deck based on current goals, risk profile, and market context.",
        "client_snapshot": {
            "name": client_name,
            "age": int(v2_data.get("client", {}).get("age", client_data.get("age", 0) or 0)),
            "dependents": int(v2_data.get("client", {}).get("dependents", client_data.get("dependents", 0) or 0)),
            "monthly_income": float(v2_data.get("client", {}).get("monthly_income", client_data.get("monthly_income", 0.0))),
            "investible_surplus": monthly_sip,
            "existing_corpus": float(v2_data.get("client", {}).get("existing_corpus", client_data.get("existing_corpus", 0.0))),
            "risk_category": str(v2_data.get("risk", {}).get("category", "Moderate")),
            "primary_goal": str((v2_data.get("goals") or [{"name": "Wealth Creation"}])[0].get("name", "Wealth Creation")),
            "source_note": _source_row("Client profile + planning engines", datetime.now().isoformat()),
        },
        "why_this_category": {
            "headline": (
                f"The proposed category mix is built for a {v2_data.get('risk', {}).get('category', 'Moderate')} investor "
                f"with inflation at {inflation_rate:.1%} and a {investment_mode.get('title', 'SIP')} deployment path."
            ),
            "narrative": investment_mode.get("description", allocation_reasoning),
            "allocation_reasoning": allocation_reasoning,
            "market_context": investment_mode.get("trigger_reason", "Current market conditions support disciplined allocation."),
            "source_note": v2_data.get("allocation", {}).get("source_note", _source_row("Allocation Engine", datetime.now().isoformat())),
        },
        "historical_performance": historical_rows,
        "historical_source_note": _source_row("Fund recommendation universe", datetime.now().isoformat()),
        "sip_illustration": {
            "rows": sip_rows,
            "source_note": _source_row("SIP illustration at 12% annualized base case", datetime.now().isoformat()),
        },
        "benchmark_comparison": benchmark_rows,
        "benchmark_source_note": _source_row("Fund benchmark enrichment", datetime.now().isoformat()),
        "advisor_contact": {
            "name": advisor_name,
            "role": advisor_role.title(),
            "email": advisor_email,
            "phone": str(client_data.get("advisor_phone") or "Contact via advisory desk"),
            "note": "For discussion, modifications, or execution support, please contact your advisor directly.",
        },
    }


def generate_proposal_deck_report(client_data, analysis_data):
    deck_data = generate_proposal_deck_data(client_data, analysis_data)
    from backend.report.pdf_generator import generate_proposal_deck_pdf

    output_path = generate_proposal_deck_pdf(deck_data=deck_data)
    with open(output_path, "rb") as pdf_file:
        return pdf_file.read()
