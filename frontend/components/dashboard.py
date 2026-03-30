import streamlit as st
from copy import deepcopy
from datetime import datetime
from config import EXCLUDE_ETF_FROM_ADVISORY
from settings import ADVANCED_PRODUCTS_ENABLED
from backend.data.benchmark_indices import enrich_with_benchmark_metrics, infer_fund_type
from backend.engines.risk_engine import compute_risk
from backend.engines.goal_engine import (
    GoalType,
    calculate_goal,
)
from backend.engines.allocation_engine import get_asset_allocation
from backend.engines.v2.portfolio_gap_advisor import PortfolioGapAdvisor
from backend.engines.monte_carlo_engine import run_monte_carlo_simulation
from backend.engines.portfolio_engine import analyze_portfolio
from backend.engines.recommendation_engine import (
    suggest_mutual_funds,
    suggest_advanced_products,
)
from backend.engines.recommendation_engine import get_processed_fund_universe
try:
    from backend.api.report_generator import (
        generate_full_report,
        generate_proposal_deck_report,
    )
except ImportError:
    generate_full_report = None
    generate_proposal_deck_report = None
from backend.scoring.monte_carlo_remediation import (
    build_sensitivity_analysis,
    generate_fix_recommendation,
)
from frontend.components.charts import (
    render_allocation_chart,
    render_projection_chart,
)
from frontend.components.projection_panels import (
    build_goal_horizon_table,
    build_projection_timeline_table,
    build_step_up_comparison_table,
    render_assumptions_box,
)
from frontend.components.sip_calculator_widget import render_sip_calculator_widget
from frontend.components.score_intelligence_panel import render_score_intelligence_panel
from frontend.api_client import (
    APIClientError,
    create_client_audit_log,
    save_client_analysis_record,
)

# ── New Intelligence Layers ───────────────────────────────────────────────────
from backend.engines.intelligence.context_engine import get_macro_context
from backend.processors.explainability import (
    explain_risk_profile,
    explain_all_funds,
    explain_portfolio_health,
)
from backend.processors.output_formatter import (
    build_projection_assumptions,
    format_macro_summary,
    format_monte_carlo_summary,
    build_insight_cards,
    build_scenario_projections,
    get_confidence_band,
)

# ── Real-Time AI Layer ──────────────────────────────────────────────────
from ai_layer import get_live_intelligence
from ai_layer.scheduler.updater import start_scheduler

# Start the background 15-minute data refresh once per app lifecycle
if "_ai_scheduler_started" not in st.session_state:
    try:
        start_scheduler()
        st.session_state["_ai_scheduler_started"] = True
    except Exception as _sched_err:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Background scheduler failed to start (external data sources may be unreachable): %s",
            _sched_err,
        )
        st.session_state["_ai_scheduler_started"] = False


def _parse_iso_timestamp(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _format_freshness_label(metric_meta: dict) -> str:
    if metric_meta.get("is_fallback"):
        return "🔴 ⚠️ Fallback data — live fetch failed"

    fetched_at = _parse_iso_timestamp(metric_meta.get("fetched_at"))
    if fetched_at is None:
        return "🟡 Cached data timestamp unavailable"

    age_seconds = max(0.0, (datetime.now() - fetched_at).total_seconds())
    if age_seconds <= 1800:
        return f"✅ Live as of {fetched_at.strftime('%H:%M')}"

    hours_ago = max(1, round(age_seconds / 3600))
    return f"🟡 Cached {hours_ago}h ago"


def _get_macro_metric_meta(macro_indicators: dict, key: str, fallback_value: float) -> dict:
    data_points = macro_indicators.get("data_points", {})
    point = data_points.get(key, {})
    return {
        "value": point.get("value", macro_indicators.get(key, fallback_value)),
        "source": point.get("source", macro_indicators.get("source", "fallback")),
        "fetched_at": point.get("fetched_at", macro_indicators.get("fetched_at")),
        "is_fallback": bool(
            point.get(
                "is_fallback",
                macro_indicators.get("source", "fallback") == "fallback",
            )
        ),
    }


def _get_vix_metric_meta(signals: dict, market_snapshot: dict) -> dict:
    vix_data = (market_snapshot or {}).get("vix", {})
    return {
        "value": float(signals.get("vix_level", vix_data.get("price", 15.0))),
        "source": vix_data.get("source", "fallback"),
        "fetched_at": vix_data.get(
            "fetched_at", (market_snapshot or {}).get("_meta", {}).get("fetched_at")
        ),
        "is_fallback": bool(vix_data.get("is_fallback", vix_data.get("source") == "fallback")),
    }


def _normalize_recommendation_weights(funds: list[dict]) -> list[dict]:
    total = sum(float(f.get("allocation_weight", 0.0)) for f in funds)
    if total <= 0:
        return funds
    normalized = []
    running = 0.0
    for idx, fund in enumerate(funds):
        cloned = dict(fund)
        if idx == len(funds) - 1:
            cloned["allocation_weight"] = round(max(0.0, 100.0 - running), 2)
        else:
            weight = round((float(fund.get("allocation_weight", 0.0)) / total) * 100.0, 2)
            cloned["allocation_weight"] = weight
            running += weight
        normalized.append(cloned)
    return normalized


def _merge_replacements(base_funds: list[dict], replacements: dict) -> list[dict]:
    merged = []
    for fund in base_funds:
        replacement = replacements.get(fund.get("name", ""))
        merged.append(replacement if replacement else fund)
    return _normalize_recommendation_weights(merged)


def _build_alternative_funds(current_fund: dict, universe_df, top_n: int = 3) -> list[dict]:
    if universe_df is None or getattr(universe_df, "empty", True):
        return []
    same_category = universe_df[universe_df["category"] == current_fund.get("category")].copy()
    same_category = same_category[
        same_category["scheme_name"] != current_fund.get("name", "")
    ].copy()
    if same_category.empty:
        return []
    same_category["fund_type"] = same_category["scheme_name"].apply(infer_fund_type)
    if EXCLUDE_ETF_FROM_ADVISORY:
        same_category = same_category[same_category["fund_type"] != "ETF"].copy()
    if same_category.empty:
        return []
    sort_col = "ranking_score" if "ranking_score" in same_category.columns else "3y"
    same_category = same_category.sort_values(by=sort_col, ascending=False).head(top_n)
    alternatives = []
    for _, row in same_category.iterrows():
        candidate = enrich_with_benchmark_metrics(
            {
                "name": row.get("scheme_name", "Unknown Fund"),
                "category": row.get("category", current_fund.get("category", "N/A")),
                "risk": current_fund.get("risk", "Moderate"),
                "allocation_weight": current_fund.get("allocation_weight", 0.0),
                "1y": row.get("1y", 0.0),
                "3y": row.get("3y", 0.0),
                "5y": row.get("5y", 0.0),
                "nav": row.get("nav", 0.0),
                "date": row.get("date", "N/A"),
                "volatility": row.get("volatility", 0.0),
                "sharpe": row.get("sharpe", 0.0),
                "score": row.get("ranking_score", row.get("score", 0.0)),
                "fund_type": row.get("fund_type", infer_fund_type(row.get("scheme_name", ""))),
                "market_reason": current_fund.get("market_reason", ""),
                "market_fit_reason": current_fund.get("market_fit_reason", ""),
            }
        )
        alternatives.append(candidate)
    return alternatives


def _normalize_goal_type_value(goal_type: str | None) -> str:
    if not goal_type:
        return GoalType.CUSTOM.value
    cleaned = str(goal_type).strip()
    if cleaned in GoalType.__members__:
        return GoalType[cleaned].value
    lowered = cleaned.lower()
    for goal_enum in GoalType:
        if goal_enum.value == lowered:
            return goal_enum.value
    return GoalType.CUSTOM.value


def _normalize_client_goals(client_data: dict) -> list[dict]:
    raw_goals = client_data.get("goals", [])
    goals: list[dict] = []

    if isinstance(raw_goals, list):
        for goal in raw_goals:
            if not isinstance(goal, dict):
                continue
            goals.append(
                {
                    "type": _normalize_goal_type_value(
                        goal.get("type") or goal.get("goal_type")
                    ),
                    "inputs": dict(goal.get("inputs") or {}),
                }
            )
        return goals

    if isinstance(raw_goals, dict):
        retirement_goal = raw_goals.get("retirement")
        if retirement_goal:
            goals.append(
                {
                    "type": GoalType.RETIREMENT.value,
                    "inputs": {
                        "current_monthly_expense": float(retirement_goal.get("expense", 50000.0)),
                        "retirement_age": int(
                            client_data.get(
                                "target_retirement_age",
                                max(60, int(client_data.get("age", 30)) + 1),
                            )
                        ),
                        "include_post_retirement_income": bool(
                            retirement_goal.get("include_post_retirement_income", False)
                        ),
                        "post_retirement_income": float(
                            retirement_goal.get("post_retirement_income", 0.0)
                        ),
                        "post_retirement_years": int(
                            retirement_goal.get("post_retirement_years", 25)
                        ),
                    },
                }
            )
        education_goal = raw_goals.get("education")
        if education_goal:
            goals.append(
                {
                    "type": GoalType.CHILD_EDUCATION.value,
                    "inputs": {
                        "target_amount": float(education_goal.get("cost", 2000000.0)),
                        "years_to_goal": int(education_goal.get("years", 12)),
                    },
                }
            )
    return goals


def _build_goal_calculation_payload(goal_entry: dict, client_data: dict, annual_step_up: float) -> dict:
    goal_type = _normalize_goal_type_value(goal_entry.get("type"))
    inputs = dict(goal_entry.get("inputs") or {})
    inputs["annual_sip_step_up"] = annual_step_up

    if goal_type == GoalType.RETIREMENT.value:
        inputs.setdefault("current_age", int(client_data.get("age", 30)))
        inputs.setdefault(
            "current_monthly_expense",
            float(inputs.get("expense", inputs.get("current_monthly_expense", 0.0))),
        )
        inputs.setdefault(
            "retirement_age",
            int(
                client_data.get(
                    "target_retirement_age",
                    max(60, int(client_data.get("age", 30)) + 1),
                )
            ),
        )
        inputs.setdefault("existing_corpus", float(client_data.get("existing_corpus", 0.0)))
    elif goal_type == GoalType.CHILD_EDUCATION.value:
        inputs.setdefault(
            "target_amount",
            float(inputs.get("present_cost", inputs.get("cost", inputs.get("target_amount", 0.0)))),
        )
        inputs.setdefault(
            "years_to_goal",
            int(inputs.get("years", inputs.get("years_to_goal", 0))),
        )
        inputs.setdefault("current_age", int(client_data.get("age", 30)))
    elif goal_type == GoalType.EMERGENCY_FUND.value:
        inputs.setdefault(
            "monthly_expenses",
            max(
                0.0,
                float(client_data.get("monthly_income", 0.0))
                - float(client_data.get("monthly_savings", 0.0)),
            ),
        )
        inputs.setdefault("months_of_coverage", int(inputs.get("months_of_coverage", 6)))
    else:
        inputs.setdefault(
            "target_amount",
            float(inputs.get("present_cost", inputs.get("cost", inputs.get("target_amount", 0.0)))),
        )
        inputs.setdefault(
            "years_to_goal",
            int(inputs.get("years", inputs.get("years_to_goal", 0))),
        )

    return inputs


def _editor_key(client_id: int | str, suffix: str) -> str:
    return f"proposal_editor_{client_id}_{suffix}"


def _allocation_input_key(client_id: int | str, asset_name: str) -> str:
    safe_asset = "".join(char.lower() if char.isalnum() else "_" for char in asset_name)
    return _editor_key(client_id, f"alloc_{safe_asset}")


def _allocations_differ(system_allocation: dict, advisor_allocation: dict, tolerance: float = 0.05) -> bool:
    keys = set(system_allocation) | set(advisor_allocation)
    return any(
        abs(float(system_allocation.get(key, 0.0)) - float(advisor_allocation.get(key, 0.0))) > tolerance
        for key in keys
    )


def _render_allocation_summary(allocation_weights: dict) -> None:
    for asset_name, weight in allocation_weights.items():
        st.markdown(f"- **{asset_name}**: {float(weight):.2f}%")


def _build_report_filename(client_data: dict, prefix: str) -> str:
    raw_name = (
        client_data.get("name")
        or client_data.get("client_name")
        or client_data.get("contact")
        or "client"
    )
    slug = "".join(char.lower() if char.isalnum() else "_" for char in str(raw_name)).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return f"{prefix}_{slug or 'client'}_{datetime.now().strftime('%Y%m%d')}.pdf"


def _auto_balance_allocations(
    client_id: int | str,
    advisor_allocation: dict,
    system_allocation: dict,
) -> None:
    total = sum(advisor_allocation.values())
    remaining = 100.0 - total

    if abs(remaining) < 0.01:
        return

    asset_names = list(advisor_allocation.keys())
    n = len(asset_names)

    if n == 0:
        return

    current_total = sum(advisor_allocation.values())
    if current_total > 0:
        normalized = {
            k: round((v / current_total) * 100, 2)
            for k, v in advisor_allocation.items()
        }
    else:
        per = round(100.0 / n, 2)
        normalized = {k: per for k in asset_names}

    st.session_state["_pending_allocation_balance"] = normalized
    st.session_state["_pending_allocation_client"] = client_id
    st.rerun()


def _build_current_portfolio_payload(client_data: dict) -> dict:
    portfolio = client_data.get("portfolio")
    if isinstance(portfolio, dict) and portfolio:
        return {
            "fd_bonds": float(portfolio.get("fd_bonds", portfolio.get("debt", 0.0)) or 0.0),
            "gold": float(portfolio.get("gold", 0.0) or 0.0),
            "cash": float(portfolio.get("cash", portfolio.get("existing_savings", 0.0)) or 0.0),
            "equity": float(portfolio.get("equity", portfolio.get("existing_mutual_funds", 0.0)) or 0.0),
        }
    return {
        "fd_bonds": float(client_data.get("existing_fd", 0.0) or 0.0),
        "gold": float(client_data.get("existing_gold", 0.0) or 0.0),
        "cash": float(client_data.get("existing_savings", 0.0) or 0.0),
        "equity": float(client_data.get("existing_mutual_funds", 0.0) or 0.0),
    }


def _build_target_allocation_payload(allocation_weights: dict) -> dict:
    target = {"equity": 0.0, "debt": 0.0, "gold": 0.0}
    for asset_name, weight in (allocation_weights or {}).items():
        lowered = str(asset_name).lower()
        numeric_weight = float(weight or 0.0)
        if "gold" in lowered:
            target["gold"] += numeric_weight
        elif "debt" in lowered or "bond" in lowered or "liquid" in lowered or "cash" in lowered:
            target["debt"] += numeric_weight
        else:
            target["equity"] += numeric_weight
    return target


def _apply_gap_recommendations(current_portfolio: dict, fund_actions: list[dict]) -> dict:
    total_corpus = sum(float(value or 0.0) for value in (current_portfolio or {}).values())
    additional_monthly_sip = sum(
        float(action.get("suggested_sip", 0.0) or 0.0)
        for action in (fund_actions or [])
        if str(action.get("action", "")).upper() in {"INCREASE", "ENTER"}
    )
    suggested_lumpsum = sum(
        float(action.get("suggested_lumpsum", 0.0) or 0.0)
        for action in (fund_actions or [])
        if str(action.get("action", "")).upper() in {"INCREASE", "ENTER"}
    )
    return {
        "initial_corpus": round(total_corpus, 2),
        "monthly_sip_increment": round(additional_monthly_sip, 2),
        "suggested_lumpsum": round(suggested_lumpsum, 2),
    }


def _log_report_issue(message: str, context: dict | None = None) -> None:
    client_id = st.session_state.get("selected_client_id")
    token = st.session_state.get("advisor_token")
    if not client_id or not token:
        return
    try:
        create_client_audit_log(
            token,
            int(client_id),
            {
                "action": "report_issue",
                "notes": message,
                "after_value": context or {},
            },
        )
    except APIClientError:
        pass


def _log_report_issued(report_type: str, version: str) -> None:
    client_id = st.session_state.get("selected_client_id")
    token = st.session_state.get("advisor_token")
    if not client_id or not token:
        return
    try:
        create_client_audit_log(
            token,
            int(client_id),
            {
                "action": "report_issued",
                "after_value": {
                    "report_type": report_type,
                    "issued_at": datetime.now().isoformat(),
                    "issued_by": st.session_state.get("advisor_name"),
                    "version": version,
                },
                "notes": f"{report_type.replace('_', ' ').title()} prepared for download.",
            },
        )
    except APIClientError:
        pass


def render_dashboard(client_data: dict):
    # ── NEW: Macro Context Engine ─────────────────────────────────────────────
    macro_context = get_macro_context()

    if macro_context.get("source") == "fallback":
        st.warning("⚠️ Using fallback macro data")
    else:
        st.success("✅ Live macro data")

    # Calculations
    user_inputs = {
        "age": client_data["age"],
        "dependents": client_data["dependents"],
        # Use absolute monthly values; the risk model normalizes savings by income.
        "income": client_data["monthly_income"],
        "savings": client_data["monthly_savings"],
        "behavior": 2 if client_data["behavior"].lower() == "moderate" else (1 if client_data["behavior"].lower() == "conservative" else 3)
    }
    risk_profile = compute_risk(user_inputs, macro_context)
    context_inflation_meta = macro_context.get(
        "inflation",
        {"value": macro_context.get("inflation_rate", 0.06), "source": "fallback", "fetched_at": None, "is_fallback": True},
    )
    context_policy_rate_meta = macro_context.get(
        "policy_rate",
        {"value": macro_context.get("interest_rate", 0.065), "source": "fallback", "fetched_at": None, "is_fallback": True},
    )

    # Pre-compute values required for the always-visible Score Intelligence Panel.
    # Important: the panel component itself does not re-compute; it only renders these precomputed values.
    portfolio_analysis = analyze_portfolio(
        existing_fd=client_data["existing_fd"],
        existing_savings=client_data["existing_savings"],
        existing_gold=client_data["existing_gold"],
        existing_mutual_funds=client_data["existing_mutual_funds"],
        risk_score=risk_profile["score"],
        monthly_income=client_data.get("monthly_income", 0.0),
        current_cpi=float(context_inflation_meta.get("value", 0.06)) * 100.0,
        goal_years=int(client_data.get("target_retirement_age", client_data["age"] + 10) - client_data["age"]),
        term_life_cover=float(client_data.get("insurance_inputs", {}).get("term_life_cover", 0.0)),
        outstanding_loans=client_data.get("insurance_inputs", {}).get("outstanding_loans", []),
    )
    effective_monthly_savings = float(
        client_data.get("effective_monthly_savings", client_data["monthly_savings"])
    )
    context_inflation_rate = float(
        context_inflation_meta.get("value", macro_context.get("inflation_rate", 0.06))
    )
    context_inflation_source = str(
        context_inflation_meta.get("source", "Fallback macro context")
    )
    projection_base_roi = 0.13
    annual_sip_step_up_pct = float(client_data.get("annual_sip_step_up_pct", 10.0))
    projection_topup_rate = max(0.0, annual_sip_step_up_pct / 100.0)

    allocation = get_asset_allocation(risk_profile["score"])
    try:
        from backend.api.advisor_overrides import apply_overrides

        allocation = apply_overrides(
            allocation if isinstance(allocation, dict) else {},
            client_data,
        )
    except Exception:
        pass
    override_applied = allocation.get("override_applied", False)
    override_reason = allocation.get("override_reason", "")
    try:
        from backend.insurance.gap_analyzer import analyze_gap

        insurance_gap = analyze_gap(client_data)
    except Exception:
        insurance_gap = {"life_gap": 0, "health_gap": 0, "status": "unavailable"}

    # Fetch recommendations first so AI layer can score them
    recommended_funds_base, is_live_data = suggest_mutual_funds(
        allocation["allocation"], risk_profile["category"]
    )
    advanced_products = (
        suggest_advanced_products(
            allocation=allocation["allocation"],
            annual_income=float(client_data.get("monthly_income", 0.0)) * 12.0,
            net_worth=float(portfolio_analysis.get("net_worth", 0.0)),
        )
        if ADVANCED_PRODUCTS_ENABLED
        else {"bonds": [], "eligibility_cards": []}
    )
    processed_universe_df, _ = get_processed_fund_universe()
    ai_intel = get_live_intelligence(
        base_allocation=allocation["allocation"],
        recommended_funds=recommended_funds_base,
        risk_category=risk_profile["category"],
        available_capital=float(client_data.get("existing_savings", 0.0)),
        use_cache=True,
    )
    signals = ai_intel.get("signals", {})
    narratives = ai_intel.get("narratives", {})
    ranked_funds = ai_intel.get("ranked_funds", recommended_funds_base)
    data_src = ai_intel.get("data_source", "fallback")
    last_upd = ai_intel.get("last_updated", "unknown")
    macro_indicators_live = ai_intel.get("macro_indicators", {})
    market_snapshot = ai_intel.get("market_snapshot", {})
    investment_mode_recommendation = ai_intel.get("investment_mode_recommendation", {})
    live_inflation_meta = _get_macro_metric_meta(macro_indicators_live, "cpi_yoy_pct", 6.0)
    live_repo_meta = _get_macro_metric_meta(macro_indicators_live, "repo_rate_pct", 6.5)
    live_bond_meta = _get_macro_metric_meta(macro_indicators_live, "bond_yield_pct", 7.1)
    vix_meta = _get_vix_metric_meta(signals, market_snapshot)
    critical_macro_fallback = any(
        item.get("is_fallback") for item in (live_inflation_meta, live_repo_meta, vix_meta)
    )

    # Goal calculations are now dynamic and driven by the saved goal list.
    goal_results = []
    ret_result = None
    probability = None
    ret_expense = None
    try:
        for goal_entry in _normalize_client_goals(client_data):
            goal_type = _normalize_goal_type_value(goal_entry.get("type"))
            goal_payload = _build_goal_calculation_payload(
                goal_entry,
                client_data,
                projection_topup_rate,
            )
            result = calculate_goal(goal_type, goal_payload, projection_base_roi)
            goal_results.append(result)
            if goal_type == GoalType.RETIREMENT.value and ret_result is None:
                ret_result = result
                ret_expense = goal_payload.get("current_monthly_expense")

        if ret_result:
            probability = run_monte_carlo_simulation(
                initial_corpus=client_data["existing_corpus"],
                monthly_sip=effective_monthly_savings,
                years=ret_result["years_to_goal"],
                target_corpus=ret_result["future_corpus"],
                expected_annual_return=projection_base_roi,
                annual_volatility=0.15,
            )
    except Exception:
        goal_results = []
        ret_result = None
        probability = None
        ret_expense = None

    # Monte Carlo fix recommendation block (Phase 6.1).
    # When success probability is very low, we must show an actionable next step
    # instead of letting the user only see the raw probability number.
    goal_fix_recommendation = None
    if ret_result is not None and probability is not None and probability < 50.0:
        current_sip = effective_monthly_savings
        required_sip = float(ret_result.get("required_sip", 0.0))
        required_corpus = float(ret_result.get("future_corpus", 0.0))
        goal_fix_recommendation = generate_fix_recommendation(
            current_sip=current_sip,
            required_sip=required_sip,
            required_corpus=required_corpus,
            current_age=int(client_data["age"]),
            retirement_age=int(client_data["target_retirement_age"]),
            current_monthly_expense=float(ret_expense or 0.0),
            existing_corpus=float(client_data["existing_corpus"]),
            expected_return=projection_base_roi,
            annual_volatility=0.15,
            gross_monthly_savings=float(client_data.get("monthly_savings", 0.0)),
            emi_total=float(client_data.get("emi_total", 0.0)),
        )

    st.markdown("---")
    st.subheader("Risk Profile Analysis")
    colA, colB = st.columns([1, 2])

    with colA:
        st.metric("Risk Category", risk_profile["category"])
        st.metric("Risk Score", f"{risk_profile['score']} / 10")

    with colB:
        # Full risk card: gauge + band thresholds + factor contribution breakdown.
        from frontend.components.risk_meter import render_risk_score_card
        render_risk_score_card(risk_profile)

    # Always-visible Score Intelligence Panel (5 scores; no extra recompute in panel)
    render_score_intelligence_panel(
        client_data=client_data,
        risk_profile=risk_profile,
        diversification=portfolio_analysis,
        macro_context=macro_context,
        ai_recommended_funds=ranked_funds,
        goal_confidence_probability=probability,
        goal_fix_recommendation=goal_fix_recommendation,
        goal_last_updated=last_upd,
    )

    # ── NEW: Risk Explainability ──────────────────────────────────────────────
    risk_xai = explain_risk_profile(risk_profile, client_data)
    with st.expander("Why is my risk level this?", expanded=False):
        st.markdown(risk_xai["summary"])
        st.markdown("**Key factors that shaped your score:**")
        for factor in risk_xai["key_factors"]:
            st.markdown(f"- {factor}")
        st.info(f"**Recommendation:** {risk_xai['recommendation']}")

        st.markdown("### 📊 Risk Factor Drivers (plain English)")
        for f in risk_profile.get("factors", []):
            st.markdown(
                f"- **{f.get('name', 'Factor')}**: {f.get('rationale', '')} "
                f"(contribution: {float(f.get('contribution', 0.0)):.2f} points)"
            )
        st.markdown(
            f"**Methodology note:** {risk_profile.get('methodology_note', '-')}"
        )
        st.markdown(f"**Allocation mapping:** {risk_profile.get('allocation_mapping', '-')}")

    # ── NEW: Macro Environment Card ────────────────────────────────────────────
    macro_fmt = format_macro_summary(macro_context)
    macro_score = macro_context.get("macro_context_score", 1.0)
    macro_colour = (
        "Strong"
        if macro_score >= 0.75
        else ("Moderate" if macro_score >= 0.50 else "Weak")
    )
    with st.expander(f"Market Environment: {macro_colour}", expanded=False):
        st.markdown(macro_fmt["simple"])
        st.markdown(macro_fmt["detailed"])
        mc_col1, mc_col2, mc_col3 = st.columns(3)
        mc_col1.metric("Macro Stability", f"{macro_context['macro_context_score']:.0%}")
        mc_col2.metric("Inflation", f"{context_inflation_meta.get('value', macro_context['inflation_rate']):.1%}")
        mc_col2.caption(_format_freshness_label(context_inflation_meta))
        mc_col3.metric(
            "Policy Rate",
            f"{context_policy_rate_meta.get('value', macro_context['interest_rate']):.2%} ({macro_context['interest_rate_trend']})",
        )
        mc_col3.caption(_format_freshness_label(context_policy_rate_meta))

    # Portfolio Health
    st.markdown("---")
    st.subheader("Existing Portfolio Health")

    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        st.metric(
            "Total Existing Corpus",
            f"₹{portfolio_analysis.get('total_corpus', 0.0):,.0f}",
        )
        st.metric(
            "Net Worth",
            f"₹{portfolio_analysis.get('net_worth', 0.0):,.0f}",
        )
        st.markdown(f"**Diversification Score:** {portfolio_analysis['diversification_score']} / 10")
        st.markdown(f"**Risk Exposure:** {portfolio_analysis.get('risk_exposure', 'N/A')}")
        if portfolio_analysis.get("total_liabilities", 0) > 0:
            st.caption(
                f"Liabilities: ₹{portfolio_analysis.get('total_liabilities', 0.0):,.0f} | EMI: ₹{portfolio_analysis.get('emi_total', 0.0):,.0f}/month"
            )

    with col_p2:
        # ── NEW: Portfolio Explainability ─────────────────────────────────────
        portfolio_xai = explain_portfolio_health(portfolio_analysis)
        st.markdown(f"**{portfolio_xai['headline']}**")
        st.markdown(portfolio_xai["narrative"])
        st.write("**Actionable Insights:**")
        severity_styles = {
            "high": ("#7f1d1d", "#fecaca"),
            "medium": ("#78350f", "#fde68a"),
            "low": ("#14532d", "#bbf7d0"),
        }
        for insight in portfolio_analysis.get("prioritized_insights", []):
            bg, border = severity_styles.get(insight.get("severity", "low"), ("#14532d", "#bbf7d0"))
            st.markdown(
                f"""
                <div style="background:{bg};border-left:4px solid {border};padding:12px 14px;border-radius:8px;margin-bottom:10px;">
                    <div style="color:{border};font-weight:600;margin-bottom:4px;">{insight.get("icon", "INFO").upper()} · {insight.get("severity", "low").capitalize()}</div>
                    <div style="color:#f8fafc;line-height:1.5;">{insight.get("message", "")}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Asset Allocation
    st.markdown("---")
    st.subheader("Quantum Asset Allocation")
    render_allocation_chart(allocation["allocation"])

    # ── NEW: Real-Time AI Intelligence Panel ─────────────────────────────────
    st.markdown("---")
    st.subheader("Live Intelligence Panel")

    # Data freshness badge
    src_badge = {
        "live": ("●", "Live data"),
        "partial": ("◐", "Partial live data"),
        "fallback": ("○", "Offline — using last known values"),
    }.get(data_src, ("○", data_src))
    st.caption(
        f"{src_badge[0]} **{src_badge[1]}** — last refreshed: `{last_upd}` (auto-refreshes every 15 min)"
    )
    if critical_macro_fallback:
        st.warning(
            "Some live market data is unavailable. Recommendations are based on last known values. Accuracy may be reduced."
        )

    # —— Row 1: Live market signal badges ————————————————————————
    if signals:
        sig_c1, sig_c2, sig_c3, sig_c4, sig_c5 = st.columns(5)
        vol_icon = {"low": "Low", "medium": "Medium", "high": "High"}.get(
            signals.get("volatility", ""), "—"
        )
        sent_icon = {
            "positive": "Positive",
            "neutral": "Neutral",
            "negative": "Negative",
        }.get(signals.get("global_sentiment", ""), "—")
        sig_c1.metric(
            "Nifty 50",
            f"₹{signals.get('nifty_price', 0):,.0f}",
            f"{signals.get('nifty_change_pct', 0):+.2f}% today",
        )
        sig_c2.metric("Market Trend", signals.get("market_trend", "—").capitalize())
        sig_c3.metric(f"Volatility (VIX)", f"{signals.get('vix_level', 0):.1f}")
        sig_c3.caption(_format_freshness_label(vix_meta))
        sig_c4.metric(
            "Global Sentiment",
            signals.get("global_sentiment", "—").capitalize(),
        )
        sig_c5.metric("USD/INR", f"₹{signals.get('usdinr_price', 0):.2f}")

        # —— Row 2: Macro metrics —————————————————————————————
        m1, m2, m3 = st.columns(3)
        m1.metric(
            "CPI Inflation (YoY)",
            f"{live_inflation_meta.get('value', signals.get('cpi_yoy_pct', 6.0)):.1f}%",
            macro_indicators_live.get("inflation_trend", "").replace("_", " ").capitalize(),
        )
        m1.caption(_format_freshness_label(live_inflation_meta))
        m2.metric(
            "RBI Repo Rate",
            f"{live_repo_meta.get('value', signals.get('repo_rate_pct', 6.5)):.2f}%",
            macro_indicators_live.get("rate_trend", "").capitalize(),
        )
        m2.caption(_format_freshness_label(live_repo_meta))
        m3.metric("10Y Bond Yield", f"{live_bond_meta.get('value', 7.1):.2f}%")
        m3.caption(_format_freshness_label(live_bond_meta))

    # —— AI Market Summary narrative ————————————————————————
    with st.expander("AI Market Narrative", expanded=True):
        st.markdown(narratives.get("market_summary", "—"))

    # —— Adaptive Allocation table ————————————————————————
    eq_d = ai_intel.get("equity_delta", 0.0)
    dbt_d = ai_intel.get("debt_delta", 0.0)
    gld_d = ai_intel.get("gold_delta", 0.0)
    if any([eq_d != 0, dbt_d != 0, gld_d != 0]):
        with st.expander("AI Allocation Adjustment (vs MPT Baseline)", expanded=False):
            st.markdown(narratives.get("allocation_rationale", ""))
            adj_cols = st.columns(3)
            adj_cols[0].metric("Equity Adjustment", f"{eq_d:+.1f}%")
            adj_cols[1].metric("Debt Adjustment", f"{dbt_d:+.1f}%")
            adj_cols[2].metric("Gold Adjustment", f"{gld_d:+.1f}%")

    # Investment Recommendations
    st.markdown("---")
    st.subheader("Smart Deployment Recommendation")
    if investment_mode_recommendation:
        mode_col1, mode_col2 = st.columns([1, 2])
        with mode_col1:
            st.metric(
                "Recommended Mode",
                investment_mode_recommendation.get("recommended_mode", "SIP"),
            )
            st.metric(
                "Market Stability",
                f"{float(investment_mode_recommendation.get('market_stability_score', 0.0)) * 100:.0f}%",
            )
        with mode_col2:
            st.markdown(
                f"**Trigger:** {investment_mode_recommendation.get('trigger_reason', '-')}"
            )
            st.markdown(
                f"**Deployment Plan:** {investment_mode_recommendation.get('deployment_plan', '-')}"
            )
            st.markdown(
                f"**Expected Advantage vs Flat SIP:** {investment_mode_recommendation.get('expected_advantage_vs_flat_sip', '-')}"
            )
    else:
        st.info("Smart deployment recommendation unavailable.")

    st.markdown("---")
    st.subheader("Portfolio Rebalancing Recommendations")
    gap_advisor = PortfolioGapAdvisor()
    current_portfolio_payload = _build_current_portfolio_payload(client_data)
    target_allocation_payload = _build_target_allocation_payload(allocation["allocation"])
    gap_recommendations = gap_advisor.compute_allocation_gap(
        current_portfolio=current_portfolio_payload,
        target_allocation=target_allocation_payload,
        total_corpus=float(portfolio_analysis.get("total_corpus", client_data.get("existing_corpus", 0.0)) or 0.0),
    )
    fund_actions = gap_advisor.recommend_funds_for_gap(
        gap_list=gap_recommendations,
        risk_profile=risk_profile,
        market_signals=macro_context,
        existing_funds=client_data.get("existing_funds", []),
    )
    rebalanced_projection = None
    improved_confidence = None
    if gap_recommendations and ret_result is not None and probability is not None:
        rebalanced_projection = _apply_gap_recommendations(
            current_portfolio_payload,
            fund_actions,
        )
        adjusted_monthly_sip = effective_monthly_savings + float(
            rebalanced_projection.get("monthly_sip_increment", 0.0)
        )
        improved_confidence = run_monte_carlo_simulation(
            initial_corpus=float(rebalanced_projection.get("initial_corpus", client_data.get("existing_corpus", 0.0))),
            monthly_sip=adjusted_monthly_sip,
            years=int(ret_result.get("years_to_goal", 0)),
            target_corpus=float(ret_result.get("future_corpus", 0.0)),
            expected_annual_return=projection_base_roi,
            annual_volatility=0.15,
        )
        if improved_confidence > probability:
            st.success(
                "Following these recommendations improves your goal confidence "
                f"from {probability:.0f}% to {improved_confidence:.0f}%."
            )
    if not fund_actions:
        st.info("No portfolio rebalancing actions are required right now.")
    else:
        action_styles = {
            "INCREASE": ("#14532d", "#bbf7d0", "🟢"),
            "ENTER": ("#14532d", "#bbf7d0", "🟢"),
            "MAINTAIN": ("#78350f", "#fde68a", "🟡"),
            "REDUCE": ("#7f1d1d", "#fecaca", "🔴"),
            "EXIT": ("#7f1d1d", "#fecaca", "🔴"),
        }
        for recommendation in fund_actions:
            action = str(recommendation.get("action", "MAINTAIN")).upper()
            bg, border, icon = action_styles.get(action, ("#334155", "#cbd5e1", "ℹ️"))
            title_parts = [f"{icon} {action}", str(recommendation.get("asset_class", "")).title()]
            if recommendation.get("fund_name"):
                title_parts.append(str(recommendation.get("fund_name")))
            details = []
            if action in {"INCREASE", "ENTER"}:
                details.append(
                    f"Suggested SIP: ₹{float(recommendation.get('suggested_sip', 0.0)):,.0f}/month"
                )
                details.append(
                    f"Suggested Lumpsum: ₹{float(recommendation.get('suggested_lumpsum', 0.0)):,.0f}"
                )
            elif action == "MAINTAIN":
                details.append("No action needed, continue current SIP.")
            else:
                if recommendation.get("replaces"):
                    details.append(f"Reduce: {recommendation.get('replaces')}")
                details.append(str(recommendation.get("rebalance_note", "")))
            benchmark_alpha = recommendation.get("benchmark_alpha")
            if benchmark_alpha not in (None, "") and action in {"INCREASE", "ENTER"}:
                details.append(f"Benchmark alpha: {float(benchmark_alpha):+.1f}%")
            st.markdown(
                f"""
                <div style="background:{bg};border-left:4px solid {border};padding:14px 16px;border-radius:8px;margin-bottom:12px;">
                    <div style="color:{border};font-weight:700;margin-bottom:6px;">{' · '.join(title_parts)}</div>
                    <div style="color:#f8fafc;line-height:1.5;margin-bottom:8px;">{recommendation.get("reason", "")}</div>
                    <div style="color:#e2e8f0;line-height:1.5;">{'<br>'.join([detail for detail in details if detail])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")
    if ADVANCED_PRODUCTS_ENABLED:
        advanced_bonds = advanced_products.get("bonds", [])
        eligibility_cards = advanced_products.get("eligibility_cards", [])
        if advanced_bonds:
            st.subheader("Advanced Investment Categories")
            st.caption("Advanced category support is enabled for this workspace.")
            st.markdown("**Bond Recommendations**")
            for bond in advanced_bonds:
                with st.expander(
                    f"{bond['name']} ({bond.get('allocation_weight', 0.0):.2f}%) - {bond['bond_type']}"
                ):
                    b1, b2, b3 = st.columns(3)
                    b1.metric("Issuer", bond.get("issuer", "N/A"))
                    b2.metric("Rating", bond.get("rating", "N/A"))
                    b3.metric("Coupon Rate", f"{bond.get('coupon_rate', 0.0):.2f}%")
                    b4, b5, b6 = st.columns(3)
                    b4.metric("YTM", f"{bond.get('ytm', 0.0):.2f}%")
                    b5.metric("Maturity Date", bond.get("maturity_date", "N/A"))
                    b6.metric("Tax Treatment", bond.get("tax_treatment", "N/A"))
        for card in advanced_products.get("eligibility_cards", []):
            st.info(f"**{card.get('title', 'Advanced Product')}**: {card.get('message', '')}")

        if advanced_bonds or eligibility_cards:
            st.markdown("---")

    st.subheader("Recommended Mutual Funds")
    st.caption(
        "AI curated funds based on your Risk Profile"
        " and Target Allocation Phase (India - 2026)"
    )
    # Use AI-ranked funds (market-aware scoring) if available
    recommended_funds = ranked_funds if ranked_funds else recommended_funds_base
    st.session_state.setdefault("fund_replacements", {})
    recommended_funds = _merge_replacements(
        recommended_funds,
        st.session_state.get("fund_replacements", {}),
    )

    if is_live_data:
        st.success("**Live NAV data from AMFI**")
        st.info("**Performance derived from high-liquidity ETF market proxy Models**")
    else:
        st.warning(
            "**Live data momentarily unavailable. Using internal fallback dataset.**"
        )
    if EXCLUDE_ETF_FROM_ADVISORY:
        st.caption("ETFs excluded from advisory model per platform policy.")

    # ── NEW: Generate XAI explanations for all funds ─────────────────────────
    fund_explanations = {e["name"]: e for e in explain_all_funds(recommended_funds)}
    # Build set of AI scores for quick lookup
    ai_scores = {f.get("name", ""): f.get("ai_score") for f in ranked_funds}

    for fund in recommended_funds:
        with st.expander(
            f"{fund['name']} ({fund['allocation_weight']}%) - {fund['category']}"
        ):
            st.write(f"**Risk Level:** {fund['risk']}")

            col_f0, col_f1, col_f2 = st.columns(3)
            col_f0.metric(
                f"NAV ({fund.get('date', 'N/A')})", f"₹{fund.get('nav', 0.0):.2f}"
            )
            col_f1.metric("Sharpe Ratio", f"{fund.get('sharpe', 0.0):.2f}")
            col_f2.metric("Annual Volatility", f"{fund.get('volatility', 0.0):.2f}%")

            st.divider()
            st.write("**Historical ETF Proxy Performance**")
            col_f3, col_f4, col_f5 = st.columns(3)
            col_f3.metric("1Y Return", f"{fund['1y']}%")
            col_f4.metric("3Y Return", f"{fund['3y']}%")
            col_f5.metric("5Y Return", f"{fund['5y']}%")

            st.write("**Benchmark Comparison**")
            bench_col1, bench_col2, bench_col3 = st.columns(3)
            bench_col1.metric("Benchmark", fund.get("benchmark_index", "N/A"))
            bench_col2.metric("Alpha 1Y", f"{fund.get('alpha_1y', 0.0):+.2f}%")
            bench_col3.metric("Alpha 3Y", f"{fund.get('alpha_3y', 0.0):+.2f}%")
            bench_col4, bench_col5, bench_col6 = st.columns(3)
            bench_col4.metric("Benchmark 1Y", f"{fund.get('benchmark_1y_return', 0.0):.2f}%")
            bench_col5.metric("Benchmark 3Y", f"{fund.get('benchmark_3y_return', 0.0):.2f}%")
            bench_col6.metric("Information Ratio", f"{fund.get('information_ratio', 0.0):.2f}")

            # ── NEW: Plain-English fund explanation + AI score ──────────────────
            ai_score = ai_scores.get(fund["name"])
            if ai_score is not None:
                st.metric(
                    "AI Market Score",
                    f"{ai_score:.1f}/100",
                    help="Composite score: 30% 1Y return + 30% 3Y return + 20% consistency + 20% market-fit",
                )
            st.divider()
            st.markdown("**Why was this fund selected for you?**")
            reason_dynamic = fund.get("reason", "")
            reason_xai = fund_explanations.get(fund["name"], {})
            market_reason = fund.get("ai_reason", "")
            rationale = reason_xai.get("rationale", {})

            # Prefer dynamic recommender's native reason, then AI Layer's reason, then static XAI
            if rationale:
                st.markdown(f"**Why selected:** {rationale.get('why_selected', '-')}")
                st.markdown(f"**Why now:** {rationale.get('why_now', '-')}")
                st.markdown(f"**Risk note:** {rationale.get('risk_note', '-')}")
            elif reason_dynamic:
                st.markdown(reason_dynamic)
            elif market_reason:
                st.markdown(market_reason)
            elif reason_xai.get("reason"):
                st.markdown(reason_xai["reason"])

            replacement_key = f"replace_{fund['name']}"
            if st.button("Replace this fund", key=replacement_key):
                st.session_state["active_replacement_fund"] = fund["name"]

            if st.session_state.get("active_replacement_fund") == fund["name"]:
                with st.sidebar:
                    st.markdown(f"### Replace {fund['name']}")
                    alternatives = _build_alternative_funds(fund, processed_universe_df, top_n=3)
                    if not alternatives:
                        st.info("No same-category alternatives available.")
                    for alt in alternatives:
                        st.markdown(f"**{alt['name']}**")
                        st.caption(
                            f"{alt['category']} | 3Y: {alt.get('3y', 0.0):.2f}% | Alpha 3Y: {alt.get('alpha_3y', 0.0):+.2f}% | IR: {alt.get('information_ratio', 0.0):.2f}"
                        )
                        if st.button("Swap In", key=f"swap_{fund['name']}_{alt['name']}"):
                            replacement = dict(alt)
                            replacement["allocation_weight"] = fund.get("allocation_weight", 0.0)
                            st.session_state["fund_replacements"][fund["name"]] = replacement
                            st.session_state["active_replacement_fund"] = None
                            st.rerun()
                    if st.button("Close Panel", key=f"close_{fund['name']}"):
                        st.session_state["active_replacement_fund"] = None
                        st.rerun()

    # Goals Analysis
    st.markdown("---")
    st.subheader("Financial Goals Analysis")
    if not goal_results:
        st.info("Add one or more goals in the client profile to see corpus and SIP analysis.")
    else:
        goal_columns = st.columns(2)
        for idx, goal_result in enumerate(goal_results):
            with goal_columns[idx % 2]:
                goal_name = str(goal_result.get("goal_name", "Goal"))
                years_to_goal = goal_result.get("years_to_goal")
                heading = f"#### {goal_name}"
                if years_to_goal is not None:
                    heading = f"{heading} ({int(years_to_goal)} Yrs)"
                st.markdown(heading)

                if goal_result.get("post_retirement_income_planning_enabled"):
                    acc_col, dist_col = st.columns(2)
                    with acc_col:
                        st.markdown("**Accumulation Phase**")
                        st.metric(
                            "Corpus needed by retirement age",
                            f"₹{goal_result.get('future_corpus', 0.0):,.0f}",
                        )
                        st.metric(
                            "Required monthly SIP",
                            f"₹{goal_result.get('required_sip', 0.0):,.0f}",
                        )
                    distribution = goal_result.get("distribution_phase", {})
                    with dist_col:
                        st.markdown("**Distribution Phase**")
                        st.metric(
                            "Corpus that will sustain income",
                            (
                                f"₹{distribution.get('annuity_corpus_required', 0.0):,.0f}"
                                f" for ₹{distribution.get('monthly_income', 0.0):,.0f}/month"
                            ),
                        )
                        gap_value = float(distribution.get("shortfall_or_surplus", 0.0))
                        gap_label = "Shortfall" if gap_value < 0 else "Surplus"
                        st.metric(gap_label, f"₹{abs(gap_value):,.0f}")
                    extra_sip = float(
                        goal_result.get("distribution_phase", {}).get(
                            "additional_sip_required", 0.0
                        )
                    )
                    years = int(goal_result.get("distribution_phase", {}).get("years", 25))
                    income_need = float(
                        goal_result.get("distribution_phase", {}).get("monthly_income", 0.0)
                    )
                    st.caption(
                        f"Corpus that will sustain ₹{income_need:,.0f}/month for {years} years is shown above."
                    )
                    if extra_sip > 0:
                        st.warning(
                            f"You need to increase your SIP by ₹{extra_sip:,.0f} to cover your post-retirement income needs."
                        )
                else:
                    st.metric(
                        "Required Future Corpus",
                        f"₹{goal_result.get('future_corpus', 0.0):,.0f}",
                    )
                    st.metric(
                        "Required Monthly SIP",
                        f"₹{goal_result.get('required_sip', 0.0):,.0f}",
                    )

                assumptions = []
                if goal_result.get("inflation_rate") is not None:
                    assumptions.append(
                        f"Inflation: {float(goal_result.get('inflation_rate', 0.0)):.1%}"
                    )
                if goal_result.get("expected_return_rate") is not None:
                    assumptions.append(
                        f"ROI: {float(goal_result.get('expected_return_rate', 0.0)):.1%}"
                    )
                if assumptions:
                    st.caption(" | ".join(assumptions))

                if goal_result.get("sip_comparison"):
                    st.markdown("**SIP Step-Up Comparison**")
                    st.dataframe(
                        build_step_up_comparison_table(goal_result["sip_comparison"]),
                        width="stretch",
                        hide_index=True,
                    )
                    st.caption(goal_result["sip_comparison"].get("note", ""))

    # Projection + confidence sections are only available if the retirement goal was set.
    if ret_result is None or probability is None:
        st.markdown("---")
        st.info("Set a retirement goal to see wealth projections, confidence, and scenario tables.")
    else:
        # Projection Chart
        st.markdown("---")
        st.subheader("SIP Projection Timeline")
        timeline_assumptions = build_projection_assumptions(
            inflation_rate=context_inflation_rate,
            inflation_source=context_inflation_source,
            roi=projection_base_roi,
            roi_basis="Retirement projection base-case assumption",
            sip_topup_rate=projection_topup_rate,
        )
        render_assumptions_box(timeline_assumptions)
        st.dataframe(
            build_projection_timeline_table(
                initial_investment=client_data["existing_corpus"],
                monthly_sip=effective_monthly_savings,
                annual_return_rate=projection_base_roi,
                years=ret_result["years_to_goal"],
            ),
            width="stretch",
            hide_index=True,
        )
        render_projection_chart(
            client_data["existing_corpus"],
            effective_monthly_savings,
            projection_base_roi,
            ret_result["years_to_goal"],
        )

        # Monte Carlo Simulation
        st.markdown("---")
        st.subheader("Monte Carlo Simulation")
        st.caption(
            "Testing 1,000 market scenarios to predict Retirement success probability."
        )

        # ── NEW: Confidence Band Badge ─────────────────────────────────────────────
        mc_fmt = format_monte_carlo_summary(probability, macro_context)
        band = get_confidence_band(probability / 100.0)
        conf_adj = macro_context.get("adjusted_confidence", 0.85)
        band_adj = get_confidence_band(conf_adj)
        cb_col1, cb_col2 = st.columns(2)
        cb_col1.metric(
            "Goal Confidence Band",
            (f"{band['icon']} {band['label']} (<50%)")
            if goal_fix_recommendation
            else f"{band['icon']} {band['label']} ({probability:.0f}%)",
            help="High = 80-100%, Medium = 50-80%, Low = <50%",
        )
        cb_col2.metric(
            "Macro-Adjusted Confidence",
            f"{band_adj['icon']} {band_adj['label']} ({conf_adj:.0%})",
            help="Confidence adjusted for current inflation, geopolitical risk, and market volatility.",
        )

        # Phase 6.1: fix recommendation block for very low confidence.
        if goal_fix_recommendation:
            st.error("❌ Low Goal Confidence: actionable fix recommendations")
            st.markdown(goal_fix_recommendation.get("gap_analysis", ""))
            st.markdown(f"**Recommended:** {goal_fix_recommendation.get('recommended', '')}")
            st.markdown(f"**Option 1:** {goal_fix_recommendation.get('option_1', '')}")
            st.markdown(f"**Option 2:** {goal_fix_recommendation.get('option_2', '')}")
            st.markdown(f"**Option 3:** {goal_fix_recommendation.get('option_3', '')}")

        st.progress(probability / 100.0)
        st.caption(mc_fmt["simple"])

        # Phase 6.1: sensitivity analysis (only when confidence is low).
        if goal_fix_recommendation:
            try:
                import plotly.graph_objects as go

                current_sip = effective_monthly_savings
                required_sip = float(ret_result.get("required_sip", 0.0))
                years = int(ret_result.get("years_to_goal", 0))
                target_corpus = float(ret_result.get("future_corpus", 0.0))
                initial_corpus = float(client_data["existing_corpus"])

                if current_sip > 0 and required_sip > 0 and years > 0 and target_corpus > 0:
                    sensitivity = build_sensitivity_analysis(
                        current_sip=current_sip,
                        required_sip=required_sip,
                        initial_corpus=initial_corpus,
                        target_corpus=target_corpus,
                        years=years,
                        expected_return=projection_base_roi,
                        annual_volatility=0.15,
                        points=10,
                    )
                    sips = sensitivity["sips"]
                    probs = sensitivity["probabilities"]

                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=sips,
                            y=probs,
                            mode="lines+markers",
                            name="Success Probability",
                        )
                    )

                    # 80% threshold highlight
                    fig.add_shape(
                        type="line",
                        x0=min(sips),
                        x1=max(sips),
                        y0=80,
                        y1=80,
                        line=dict(color="red", width=2, dash="dash"),
                    )

                    # Mark current position
                    fig.add_trace(
                        go.Scatter(
                            x=[current_sip],
                            y=[sensitivity["current_probability"]],
                            mode="markers",
                            marker=dict(color="green", size=10),
                            name="Current SIP",
                        )
                    )

                    fig.update_layout(
                        title="Sensitivity Analysis: SIP Amount vs Success Probability",
                        xaxis_title="Monthly SIP Amount (INR)",
                        yaxis_title="Success Probability (%)",
                        template="plotly_dark",
                        height=320,
                    )
                    st.plotly_chart(fig, width="stretch")
            except Exception:
                st.caption("Sensitivity analysis unavailable.")

        if probability > 80:
            st.success(
                f"**{probability}%** probability of achieving your corpus! "
                "You are on a highly secure path."
            )
        elif probability > 50:
            st.warning(
                f"**{probability}%** probability of achieving your corpus. "
                "Consider increasing your SIP for more certainty."
            )
        else:
            st.error(
                f"**{probability}%** probability of achieving your corpus. "
                "A strategy adjustment is highly recommended."
            )

        # ── NEW: Scenario Projections Table ───────────────────────────────────────
        st.markdown("---")
        st.subheader("Expected Returns (Goal Horizon)")
        st.caption(
            "How your wealth could grow under different market conditions over your investment horizon."
        )
        scenario_probabilities = {}
        for scenario_name, annual_rate in (
            ("conservative", 0.08),
            ("moderate", 0.12),
            ("aggressive", 0.15),
        ):
            scenario_probabilities[scenario_name] = run_monte_carlo_simulation(
                initial_corpus=client_data["existing_corpus"],
                monthly_sip=effective_monthly_savings,
                years=ret_result["years_to_goal"],
                target_corpus=ret_result["future_corpus"],
                expected_annual_return=annual_rate,
                annual_volatility=0.15,
            )
        scenarios = build_scenario_projections(
            existing_corpus=client_data["existing_corpus"],
            monthly_sip=effective_monthly_savings,
            years=ret_result["years_to_goal"],
            inflation_rate=context_inflation_rate,
            success_probabilities=scenario_probabilities,
        )
        scenario_assumptions = build_projection_assumptions(
            inflation_rate=context_inflation_rate,
            inflation_source=context_inflation_source,
            roi=0.12,
            roi_basis="Goal-horizon moderate scenario assumption",
            sip_topup_rate=projection_topup_rate,
        )
        render_assumptions_box(scenario_assumptions)
        st.dataframe(
            build_goal_horizon_table(scenarios),
            width="stretch",
            hide_index=True,
        )

        # ── NEW: AI Insight Cards ──────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("AI Insight Cards")
        insight_cards = build_insight_cards(
            risk_data=risk_profile,
            probability=probability,
            portfolio_data=portfolio_analysis,
            macro_context=macro_context,
        )
        card_cols = st.columns(3)
        colour_map = {"green": "[OK]", "yellow": "[!]", "red": "[!!]"}
        for i, card in enumerate(insight_cards):
            with card_cols[i]:
                icon_prefix = colour_map.get(card["colour"], "")
                st.metric(
                    label=f"{card['title']}",
                    value=card["value"],
                )
                st.caption(f"{icon_prefix} {card['recommendation']}")

    # SIP Calculator Widget
    st.markdown("---")
    st.subheader("Interactive Scenario Builder")
    render_sip_calculator_widget(macro_context=macro_context)

    goal_results_payload = goal_results
    analysis_results = {
        "risk": risk_profile,
        "goals": goal_results_payload,
        "portfolio": portfolio_analysis,
        "portfolio_rebalancing": {
            "gaps": gap_recommendations,
            "fund_actions": fund_actions,
        },
        "allocation": allocation,
        "insurance": insurance_gap,
        "macro": macro_context,
        "funds": recommended_funds,
        "advanced_products": advanced_products,
        "investment_mode_recommendation": investment_mode_recommendation,
        "monte_carlo": {
            "success_probability": probability,
            "fix_recommendation": goal_fix_recommendation,
        }
        if probability is not None
        else {},
    }
    proposal_draft_payload = {
        "generated_at": datetime.now().isoformat(),
        "risk_profile": risk_profile,
        "goal_results": goal_results_payload,
        "portfolio_health": portfolio_analysis,
        "portfolio_rebalancing": {
            "gaps": gap_recommendations,
            "fund_actions": fund_actions,
        },
        "target_allocation": allocation,
        "insurance_gap": insurance_gap,
        "recommended_funds": recommended_funds,
        "advanced_products": advanced_products,
        "investment_mode_recommendation": investment_mode_recommendation,
        "macro_context": macro_context,
        "monte_carlo": {
            "success_probability": probability,
            "fix_recommendation": goal_fix_recommendation,
        }
        if probability is not None
        else {},
    }

    st.markdown("---")
    st.subheader("Proposal Review")
    st.caption("System Draft is generated automatically. Advisor Final is the reviewed client-facing recommendation.")

    selected_client_id = st.session_state.get("selected_client_id", "current")
    saved_proposal = (
        ((st.session_state.get("selected_client_record") or {}).get("analysis") or {}).get("proposal_draft")
        or {}
    )
    saved_advisor_final = saved_proposal.get("advisor_final") or {}
    saved_override_reason = saved_proposal.get("override_reason") or ""
    system_risk_class = str(risk_profile.get("category", "Moderate"))
    system_allocation_weights = dict(allocation.get("allocation", {}))
    risk_key = _editor_key(selected_client_id, "risk_class")
    reason_key = _editor_key(selected_client_id, "override_reason")

    # Apply pending auto-balance before widgets render
    pending = st.session_state.pop("_pending_allocation_balance", None)
    pending_client = st.session_state.pop("_pending_allocation_client", None)
    if pending and pending_client == selected_client_id:
        for asset_name, weight in pending.items():
            asset_key = (
                f"proposal_editor_{selected_client_id}_alloc_"
                f"{asset_name.lower().replace(' ', '_').replace('-', '_').replace('/', '_')}"
            )
            st.session_state[asset_key] = weight

    if risk_key not in st.session_state:
        st.session_state[risk_key] = str(
            saved_advisor_final.get("risk_class")
            or saved_advisor_final.get("risk_profile", {}).get("category")
            or system_risk_class
        )
    if reason_key not in st.session_state:
        st.session_state[reason_key] = saved_override_reason
    for asset_name, default_weight in system_allocation_weights.items():
        asset_key = _allocation_input_key(selected_client_id, asset_name)
        if asset_key not in st.session_state:
            st.session_state[asset_key] = float(
                (saved_advisor_final.get("allocation") or {}).get(
                    asset_name,
                    (saved_advisor_final.get("target_allocation", {}).get("allocation") or {}).get(
                        asset_name,
                        default_weight,
                    ),
                )
            )

    if st.button("Reset Advisor Final to System Draft", key=_editor_key(selected_client_id, "reset")):
        st.session_state[risk_key] = system_risk_class
        st.session_state[reason_key] = saved_override_reason
        for asset_name, default_weight in system_allocation_weights.items():
            st.session_state[_allocation_input_key(selected_client_id, asset_name)] = float(default_weight)
        st.rerun()

    system_col, final_col = st.columns(2)
    with system_col:
        st.markdown("#### System Draft")
        st.metric("Risk Class", system_risk_class)
        st.metric("Risk Score", f"{float(risk_profile.get('score', 0.0)):.1f} / 10")
        st.markdown("**Allocation Recommendation**")
        _render_allocation_summary(system_allocation_weights)

    with final_col:
        st.markdown("#### Advisor Final")
        advisor_final_risk_class = st.selectbox(
            "Final Risk Class",
            ["Conservative", "Moderate", "Aggressive"],
            key=risk_key,
        )
        st.markdown("**Final Allocation**")
        advisor_final_allocation: dict[str, float] = {}
        for asset_name in system_allocation_weights:
            asset_key = _allocation_input_key(selected_client_id, asset_name)
            advisor_final_allocation[asset_name] = float(
                st.number_input(
                    f"{asset_name} (%)",
                    min_value=0.0,
                    max_value=100.0,
                    step=0.5,
                    key=asset_key,
                )
            )
        override_reason_text = st.text_area(
            "Override Reason",
            key=reason_key,
            help="Required before changing risk class or allocation from the system draft.",
        )

    risk_override_changed = advisor_final_risk_class != system_risk_class
    allocation_override_changed = _allocations_differ(
        system_allocation_weights,
        advisor_final_allocation,
    )
    advisor_allocation_total = round(sum(advisor_final_allocation.values()), 2)
    override_required = risk_override_changed or allocation_override_changed
    override_reason_clean = override_reason_text.strip()

    if abs(advisor_allocation_total - 100.0) > 0.1:
        error_col, action_col = st.columns([3, 1])
        error_col.error(
            f"Advisor Final allocation must total 100%. Current total: {advisor_allocation_total:.2f}%."
        )
        if action_col.button("Auto-balance remaining", key=_editor_key(selected_client_id, "auto_balance")):
            _auto_balance_allocations(
                selected_client_id,
                advisor_final_allocation,
                system_allocation_weights,
            )
            st.rerun()
    elif override_required and not override_reason_clean:
        st.warning("Enter an override reason before saving changes to risk class or allocation.")
    elif override_required:
        st.info("Override reason captured. Both System Draft and Advisor Final will be stored.")
    else:
        st.success("Advisor Final currently matches the System Draft.")

    advisor_final_payload = deepcopy(proposal_draft_payload)
    advisor_final_payload["risk_class"] = advisor_final_risk_class
    advisor_final_payload["risk_profile"] = {
        **deepcopy(risk_profile),
        "category": advisor_final_risk_class,
        "override_reason": override_reason_clean or None,
    }
    advisor_final_payload["allocation"] = dict(advisor_final_allocation)
    advisor_final_payload["target_allocation"] = {
        **deepcopy(allocation),
        "allocation": dict(advisor_final_allocation),
        "override_applied": override_required,
        "override_reason": override_reason_clean or "",
    }
    advisor_final_payload["advisor_review"] = {
        "reviewed_by": st.session_state.get("advisor_name"),
        "reviewed_role": st.session_state.get("advisor_role"),
        "reviewed_at": datetime.now().isoformat(),
        "override_reason": override_reason_clean or None,
        "changed_fields": {
            "risk_class": risk_override_changed,
            "allocation": allocation_override_changed,
        },
    }

    st.markdown("---")
    st.subheader("Client Record")
    if st.session_state.get("advisor_token") and st.session_state.get("selected_client_id"):
        if st.button("Save to Client Record", width="stretch"):
            if abs(advisor_allocation_total - 100.0) > 0.1:
                st.error(
                    f"Unable to save. Advisor Final allocation must total 100%. Current total: {advisor_allocation_total:.2f}%."
                )
                return
            if override_required and not override_reason_clean:
                st.error("Unable to save. Override reason is required when risk class or allocation changes.")
                return
            with st.spinner("Saving analysis to client record..."):
                try:
                    save_response = save_client_analysis_record(
                        st.session_state["advisor_token"],
                        int(st.session_state["selected_client_id"]),
                        {
                            "risk": risk_profile,
                            "goals": goal_results_payload,
                            "portfolio": portfolio_analysis,
                            "proposal_draft": proposal_draft_payload,
                            "advisor_final": advisor_final_payload,
                            "override_reason": override_reason_clean or None,
                            "proposal_status": "overridden" if override_required else "reviewed",
                            "client_profile": client_data,
                        },
                    )
                except APIClientError as exc:
                    st.error(f"Unable to save client analysis: {exc}")
                else:
                    selected_record = dict(st.session_state.get("selected_client_record") or {})
                    analysis_section = dict(selected_record.get("analysis") or {})
                    analysis_section["proposal_draft"] = {
                        "system_draft": proposal_draft_payload,
                        "advisor_final": advisor_final_payload,
                        "override_reason": override_reason_clean or None,
                        "status": "overridden" if override_required else "reviewed",
                        "created_at": save_response.get("saved_at"),
                    }
                    selected_record["analysis"] = analysis_section
                    st.session_state["selected_client_record"] = selected_record
                    st.success(
                        f"Analysis saved to client record at {save_response.get('saved_at', 'now')}."
                    )
    else:
        st.info("Client record saving is available after advisor login and client selection.")

    # Generate PDF Report
    st.markdown("---")
    st.subheader("Client Investment Proposal")

    if st.button("Generate Detailed PDF Report"):
        st.session_state["pending_pdf_generation"] = True

    if st.session_state.get("pending_pdf_generation"):
        if ret_result is None or probability is None:
            st.info("Set a retirement goal to generate the PDF proposal.")
            st.session_state["pending_pdf_generation"] = False
        else:
            if generate_full_report is None:
                st.error("Report generator unavailable — missing dependency.")
            else:
                with st.spinner("Generating proposal..."):
                    try:
                        report_context = dict(analysis_results)
                        if critical_macro_fallback:
                            critical_fetch_times = [
                                _parse_iso_timestamp(item.get("fetched_at"))
                                for item in (live_inflation_meta, live_repo_meta, vix_meta)
                                if item.get("fetched_at")
                            ]
                            oldest_fetch_time = (
                                min(critical_fetch_times).strftime("%Y-%m-%d %H:%M")
                                if critical_fetch_times
                                else "timestamp unavailable"
                            )
                            st.warning(
                                "⚠️ Report generated using cached macro data "
                                f"(last updated: {oldest_fetch_time}). "
                                "Live data was unavailable at time of generation.",
                                icon="⚠️",
                            )
                            report_context["data_freshness_note"] = (
                                "Macro data cached — live fetch unavailable at generation time."
                            )
                        report_client_data = {
                            **client_data,
                            "monthly_savings": effective_monthly_savings,
                            "advisor_name": st.session_state.get("advisor_name"),
                            "advisor_email": st.session_state.get("advisor_email"),
                            "advisor_role": st.session_state.get("advisor_role"),
                        }
                        pdf_bytes = generate_full_report(
                            report_client_data, report_context
                        )
                        if pdf_bytes:
                            report_version = datetime.now().strftime("%Y%m%d%H%M%S")
                            st.download_button(
                                label="📄 Download PDF Report",
                                data=pdf_bytes,
                                file_name=_build_report_filename(client_data, "financial_report"),
                                mime="application/pdf",
                            )
                            _log_report_issued("detailed_report", report_version)
                        else:
                            _log_report_issue(
                                "Detailed PDF generation returned no output.",
                                {"report_type": "detailed_pdf"},
                            )
                            st.error("Report generation failed — no output returned.")
                    except Exception as e:
                        _log_report_issue(
                            f"Detailed PDF generation error: {e}",
                            {"report_type": "detailed_pdf"},
                        )
                        st.error(f"Report generation error: {e}")
            st.session_state["pending_pdf_generation"] = False

    # --- Insurance Gap Analysis & Advisor Overrides (non-blocking) ---
    st.markdown("### 🛡️ Insurance Gap")
    try:
        st.metric("Life Cover Gap", f"₹{insurance_gap.get('life_gap', 0):,.0f}")
        st.metric("Health Cover Gap", f"₹{insurance_gap.get('health_gap', 0):,.0f}")
        if client_data.get("emi_total", 0) > 0:
            st.caption(
                f"₹{client_data.get('emi_total', 0.0):,.0f}/month EMI deducted from savings capacity."
            )
    except:
        st.write("Insurance data unavailable")

    if override_applied:
        st.warning(f"Advisor Adjustment: {override_reason}")

    st.markdown("---")
    if st.button("Download Advanced Report"):
        if generate_full_report is None:
            st.error("Report generator unavailable — missing dependency.")
        else:
            with st.spinner("Generating report..."):
                try:
                    report_context = {
                        **analysis_results,
                        "insurance": insurance_gap,
                    }
                    if critical_macro_fallback:
                        critical_fetch_times = [
                            _parse_iso_timestamp(item.get("fetched_at"))
                            for item in (live_inflation_meta, live_repo_meta, vix_meta)
                            if item.get("fetched_at")
                        ]
                        oldest_fetch_time = (
                            min(critical_fetch_times).strftime("%Y-%m-%d %H:%M")
                            if critical_fetch_times
                            else "timestamp unavailable"
                        )
                        st.warning(
                            "⚠️ Report generated using cached macro data "
                            f"(last updated: {oldest_fetch_time}). "
                            "Live data was unavailable at time of generation.",
                            icon="⚠️",
                        )
                        report_context["data_freshness_note"] = (
                            "Macro data cached — live fetch unavailable at generation time."
                        )
                    report_client_data = {
                        **client_data,
                        "monthly_savings": effective_monthly_savings,
                        "advisor_name": st.session_state.get("advisor_name"),
                        "advisor_email": st.session_state.get("advisor_email"),
                        "advisor_role": st.session_state.get("advisor_role"),
                    }
                    pdf_bytes = generate_full_report(
                        report_client_data,
                        report_context,
                    )
                    if pdf_bytes:
                        report_version = datetime.now().strftime("%Y%m%d%H%M%S")
                        st.download_button(
                            label="📄 Download PDF Report",
                            data=pdf_bytes,
                            file_name=_build_report_filename(client_data, "financial_report"),
                            mime="application/pdf"
                        )
                        _log_report_issued("advanced_report", report_version)
                    else:
                        _log_report_issue(
                            "Advanced report generation returned no output.",
                            {"report_type": "advanced_report"},
                        )
                        st.error("Report generation failed — no output returned.")
                except Exception as e:
                    _log_report_issue(
                        f"Advanced report generation error: {e}",
                        {"report_type": "advanced_report"},
                    )
                    st.error(f"Report generation error: {e}")

    st.markdown("---")
    st.subheader("Shareable Advisor Deck")
    if st.button("Generate Advisor Deck PDF"):
        if generate_proposal_deck_report is None:
            st.error("Report generator unavailable — missing dependency.")
        else:
            with st.spinner("Generating advisor deck..."):
                try:
                    deck_client_data = {
                        **client_data,
                        "monthly_savings": effective_monthly_savings,
                        "advisor_name": st.session_state.get("advisor_name"),
                        "advisor_email": st.session_state.get("advisor_email"),
                        "advisor_role": st.session_state.get("advisor_role"),
                    }
                    deck_bytes = generate_proposal_deck_report(
                        deck_client_data,
                        analysis_results,
                    )
                    if deck_bytes:
                        report_version = datetime.now().strftime("%Y%m%d%H%M%S")
                        st.download_button(
                            label="📊 Download Advisor Deck",
                            data=deck_bytes,
                            file_name=_build_report_filename(client_data, "advisor_deck"),
                            mime="application/pdf",
                        )
                        _log_report_issued("advisor_deck", report_version)
                    else:
                        _log_report_issue(
                            "Advisor deck generation returned no output.",
                            {"report_type": "advisor_deck"},
                        )
                        st.error("Advisor deck generation failed — no output returned.")
                except Exception as e:
                    _log_report_issue(
                        f"Advisor deck generation error: {e}",
                        {"report_type": "advisor_deck"},
                    )
                    st.error(f"Advisor deck generation error: {e}")
