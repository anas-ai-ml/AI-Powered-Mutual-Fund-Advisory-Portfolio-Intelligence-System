import streamlit as st
from datetime import datetime
from backend.engines.risk_engine import compute_risk
from backend.engines.goal_engine import (
    calculate_retirement_goal,
    calculate_child_education_goal,
)
from backend.engines.allocation_engine import get_asset_allocation
from backend.engines.monte_carlo_engine import run_monte_carlo_simulation
from backend.engines.portfolio_engine import analyze_portfolio
from backend.engines.recommendation_engine import suggest_mutual_funds
from backend.api.report_generator import generate_full_report
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
    start_scheduler()
    st.session_state["_ai_scheduler_started"] = True


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

    # Fetch recommendations first so AI layer can score them
    recommended_funds_base, is_live_data = suggest_mutual_funds(
        allocation["allocation"], risk_profile["category"]
    )
    ai_intel = get_live_intelligence(
        base_allocation=allocation["allocation"],
        recommended_funds=recommended_funds_base,
        risk_category=risk_profile["category"],
        use_cache=True,
    )
    signals = ai_intel.get("signals", {})
    narratives = ai_intel.get("narratives", {})
    ranked_funds = ai_intel.get("ranked_funds", recommended_funds_base)
    data_src = ai_intel.get("data_source", "fallback")
    last_upd = ai_intel.get("last_updated", "unknown")
    macro_indicators_live = ai_intel.get("macro_indicators", {})
    market_snapshot = ai_intel.get("market_snapshot", {})
    live_inflation_meta = _get_macro_metric_meta(macro_indicators_live, "cpi_yoy_pct", 6.0)
    live_repo_meta = _get_macro_metric_meta(macro_indicators_live, "repo_rate_pct", 6.5)
    live_bond_meta = _get_macro_metric_meta(macro_indicators_live, "bond_yield_pct", 7.1)
    vix_meta = _get_vix_metric_meta(signals, market_snapshot)
    critical_macro_fallback = any(
        item.get("is_fallback") for item in (live_inflation_meta, live_repo_meta, vix_meta)
    )

    # Goal Confidence Band: only available if a retirement goal is set.
    ret_result = None
    probability = None
    ret_expense = None
    try:
        goals = client_data.get("goals", {})
        ret_data = goals.get("retirement")
        if ret_data:
            ret_expense = ret_data.get("expense")
            ret_result = calculate_retirement_goal(
                current_age=client_data["age"],
                current_monthly_expense=ret_expense,
                expected_return_rate=projection_base_roi,
                retirement_age=client_data["target_retirement_age"],
                existing_corpus=client_data["existing_corpus"],
                post_retirement_income=ret_data.get("post_retirement_income"),
                post_retirement_years=int(ret_data.get("post_retirement_years", 25)),
                include_post_retirement_income=bool(
                    ret_data.get("include_post_retirement_income", False)
                ),
                annual_sip_step_up=projection_topup_rate,
            )
            probability = run_monte_carlo_simulation(
                initial_corpus=client_data["existing_corpus"],
                monthly_sip=effective_monthly_savings,
                years=ret_result["years_to_goal"],
                target_corpus=ret_result["future_corpus"],
                expected_annual_return=projection_base_roi,
                annual_volatility=0.15,
            )
    except Exception:
        ret_result = None
        probability = None
        ret_expense = None

    # Monte Carlo fix recommendation block (Phase 6.1).
    # When success probability is very low, we must show an actionable next step
    # instead of letting the user only see the raw probability number.
    goal_fix_recommendation = None
    if ret_result is not None and probability is not None and probability < 50.0:
        from backend.utils.sip_calculator import calculate_sip_future_value

        current_sip = effective_monthly_savings
        required_sip = float(ret_result.get("required_sip", 0.0))
        required_corpus = float(ret_result.get("future_corpus", 0.0))
        years = int(ret_result.get("years_to_goal", 0))

        pct = (current_sip / required_sip) if required_sip > 0 else 0.0
        gap_sip = max(0.0, required_sip - current_sip)

        # Option 1: Increase SIP to cover the SIP gap
        option_1 = (
            f"Increase monthly savings by ₹{gap_sip:,.0f} "
            f"to meet the ₹{required_corpus:,.0f} corpus target."
        )

        # Option 2: Extend retirement age until required SIP fits capacity
        extra_years = 0
        adjusted_sip = required_sip
        if ret_expense is not None:
            base_ret_age = int(client_data["target_retirement_age"])
            # Try up to 5 extra years to avoid excessive computation.
            for k in range(1, 6):
                new_ret_age = base_ret_age + k
                new_ret = calculate_retirement_goal(
                    current_age=client_data["age"],
                    current_monthly_expense=ret_expense,
                    expected_return_rate=projection_base_roi,
                    retirement_age=new_ret_age,
                    existing_corpus=client_data["existing_corpus"],
                )
                new_required_sip = float(new_ret.get("required_sip", required_sip))
                if new_required_sip <= current_sip:
                    extra_years = k
                    adjusted_sip = new_required_sip
                    break
                adjusted_sip = new_required_sip
            if extra_years == 0:
                # If we didn't find a fit, still propose the 5-year extension.
                extra_years = 5
                adjusted_sip = adjusted_sip

        option_2 = (
            f"Extend retirement age by {extra_years} years — "
            f"required SIP drops to ₹{adjusted_sip:,.0f}/month."
        )

        # Option 3: Reduce target corpus to what current SIP can achieve (Monte Carlo re-check)
        existing_corpus = float(client_data["existing_corpus"])
        expected_annual_return = projection_base_roi
        annual_volatility = 0.15

        # Achievable corpus at horizon using current SIP for the "shortfall" portion.
        fv_existing = existing_corpus * ((1 + expected_annual_return) ** years)
        fv_shortfall_sip = calculate_sip_future_value(
            current_sip, expected_annual_return, years
        )
        achievable_corpus = fv_existing + fv_shortfall_sip

        new_probability = run_monte_carlo_simulation(
            initial_corpus=existing_corpus,
            monthly_sip=current_sip,
            years=years,
            target_corpus=achievable_corpus,
            expected_annual_return=expected_annual_return,
            annual_volatility=annual_volatility,
        )

        option_3 = (
            f"Reduce retirement corpus target to ₹{achievable_corpus:,.0f} "
            f"(achievable at ₹{current_sip:,.0f}/month SIP = {new_probability:.0f}% confidence)."
        )

        recommended = "option_2"
        gap_analysis = (
            f"Your current SIP capacity (₹{current_sip:,.0f}) covers "
            f"{pct:.0%} of the required SIP (₹{required_sip:,.0f}). "
            f"Gap: ₹{gap_sip:,.0f}/month."
        )

        goal_fix_recommendation = {
            "gap_analysis": gap_analysis,
            "option_1": option_1,
            "option_2": option_2,
            "option_3": option_3,
            "recommended": recommended,
        }

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
    st.subheader("Recommended Mutual Funds")
    st.caption(
        "AI curated funds based on your Risk Profile"
        " and Target Allocation Phase (India - 2026)"
    )
    # Use AI-ranked funds (market-aware scoring) if available
    recommended_funds = ranked_funds if ranked_funds else recommended_funds_base

    if is_live_data:
        st.success("**Live NAV data from AMFI**")
        st.info("**Performance derived from high-liquidity ETF market proxy Models**")
    else:
        st.warning(
            "**Live data momentarily unavailable. Using internal fallback dataset.**"
        )

    # ── NEW: Generate XAI explanations for all funds ─────────────────────────
    fund_explanations = {
        e["name"]: e["reason"] for e in explain_all_funds(recommended_funds)
    }
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
            reason_xai = fund_explanations.get(fund["name"], "")
            market_reason = fund.get("ai_reason", "")

            # Prefer dynamic recommender's native reason, then AI Layer's reason, then static XAI
            if reason_dynamic:
                st.markdown(reason_dynamic)
            elif market_reason:
                st.markdown(market_reason)
            elif reason_xai:
                st.markdown(reason_xai)

    # Goals Analysis
    st.markdown("---")
    st.subheader("Financial Goals Analysis")
    col1, col2 = st.columns(2)

    with col1:
        if ret_result is None:
            st.markdown("#### Retirement (Goal not set)")
            st.info("Set a retirement goal to see required corpus and SIP.")
        else:
            st.markdown(f"#### Retirement ({ret_result['years_to_goal']} Yrs)")
            if ret_result.get("post_retirement_income_planning_enabled"):
                acc_col, dist_col = st.columns(2)
                with acc_col:
                    st.markdown("**Accumulation Phase**")
                    st.metric(
                        "Corpus needed by retirement age",
                        f"₹{ret_result['future_corpus']:,.0f}",
                    )
                    st.metric(
                        "Required monthly SIP",
                        f"₹{ret_result['required_sip']:,.0f}",
                    )
                distribution = ret_result.get("distribution_phase", {})
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
                    ret_result.get("distribution_phase", {}).get(
                        "additional_sip_required", 0.0
                    )
                )
                years = int(ret_result.get("distribution_phase", {}).get("years", 25))
                income_need = float(
                    ret_result.get("distribution_phase", {}).get("monthly_income", 0.0)
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
                    "Required Future Corpus", f"₹{ret_result['future_corpus']:,.0f}"
                )
                st.metric("Required Monthly SIP", f"₹{ret_result['required_sip']:,.0f}")
            if ret_result.get("sip_comparison"):
                st.markdown("**SIP Step-Up Comparison**")
                st.dataframe(
                    build_step_up_comparison_table(ret_result["sip_comparison"]),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(ret_result["sip_comparison"].get("note", ""))

    edu_data = client_data["goals"]["education"]
    edu_result = calculate_child_education_goal(
        edu_data["cost"],
        edu_data["years"],
        expected_return_rate=projection_base_roi,
        annual_sip_step_up=projection_topup_rate,
    )

    with col2:
        st.markdown(f"#### Education ({edu_result['years_to_goal']} Yrs)")
        st.metric("Required Future Corpus", f"₹{edu_result['future_corpus']:,.0f}")
        st.metric("Required Monthly SIP", f"₹{edu_result['required_sip']:,.0f}")
        if edu_result.get("sip_comparison"):
            st.markdown("**SIP Step-Up Comparison**")
            st.dataframe(
                build_step_up_comparison_table(edu_result["sip_comparison"]),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(edu_result["sip_comparison"].get("note", ""))

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
            use_container_width=True,
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
                import numpy as np
                import plotly.graph_objects as go

                current_sip = effective_monthly_savings
                required_sip = float(ret_result.get("required_sip", 0.0))
                years = int(ret_result.get("years_to_goal", 0))
                target_corpus = float(ret_result.get("future_corpus", 0.0))
                initial_corpus = float(client_data["existing_corpus"])

                if current_sip > 0 and required_sip > 0 and years > 0 and target_corpus > 0:
                    max_sip = min(2.0 * required_sip, 2.0 * current_sip)
                    sips = np.linspace(current_sip, max_sip, 10)
                    probs = [
                        run_monte_carlo_simulation(
                            initial_corpus=initial_corpus,
                            monthly_sip=float(sip),
                            years=years,
                            target_corpus=target_corpus,
                            expected_annual_return=projection_base_roi,
                            annual_volatility=0.15,
                        )
                        for sip in sips
                    ]

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
                            y=[run_monte_carlo_simulation(
                                initial_corpus=initial_corpus,
                                monthly_sip=current_sip,
                                years=years,
                                target_corpus=target_corpus,
                                expected_annual_return=projection_base_roi,
                                annual_volatility=0.15,
                            )],
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
            use_container_width=True,
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

    # Generate PDF Report
    st.markdown("---")
    st.subheader("Client Investment Proposal")

    if st.button("Generate Detailed PDF Report"):
        st.session_state["pending_pdf_generation"] = True

    if st.session_state.get("pending_pdf_generation"):
        if ret_result is None or probability is None:
            st.info("Set a retirement goal to generate the PDF proposal.")
            st.session_state["pending_pdf_generation"] = False
        elif critical_macro_fallback and not st.session_state.get("stale_pdf_confirmed"):
            st.warning(
                "Live market data is stale. Generate report with cached data?"
            )
            confirm_col1, confirm_col2 = st.columns(2)
            if confirm_col1.button("Proceed", key="confirm_stale_pdf"):
                st.session_state["stale_pdf_confirmed"] = True
                st.rerun()
            if confirm_col2.button("Wait for Live Data", key="cancel_stale_pdf"):
                st.session_state["pending_pdf_generation"] = False
                st.session_state["stale_pdf_confirmed"] = False
                st.rerun()
        else:
            with st.spinner("Generating proposal..."):
                analysis_results = {
                    "risk": risk_profile,
                    "goals": [ret_result, edu_result],
                    "portfolio": portfolio_analysis,
                    "macro": macro_context,
                    "funds": recommended_funds,
                    "monte_carlo": {"success_probability": probability},
                }

                try:
                    report_client_data = {
                        **client_data,
                        "monthly_savings": effective_monthly_savings,
                    }
                    pdf_bytes = generate_full_report(report_client_data, analysis_results)
                    if pdf_bytes:
                        st.download_button(
                            label="📄 Download PDF Report",
                            data=pdf_bytes,
                            file_name=f"financial_report_{client_data.get('marital_status', 'client').lower()}_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                        )
                    else:
                        st.error("Report generation failed — no output returned.")
                except Exception as e:
                    st.error(f"Report generation error: {e}")
            st.session_state["pending_pdf_generation"] = False
            st.session_state["stale_pdf_confirmed"] = False

    # --- Insurance Gap Analysis & Advisor Overrides (non-blocking) ---
    try:
        from backend.insurance.gap_analyzer import analyze_gap
        insurance_gap = analyze_gap(client_data)
    except Exception:
        insurance_gap = {"life_gap": 0, "health_gap": 0, "status": "unavailable"}

    st.markdown("### 🛡️ Insurance Gap")
    try:
        st.metric("Life Cover Gap", insurance_gap.get("life_gap", 0))
        st.metric("Health Cover Gap", insurance_gap.get("health_gap", 0))
        if client_data.get("emi_total", 0) > 0:
            st.caption(
                f"₹{client_data.get('emi_total', 0.0):,.0f}/month EMI deducted from savings capacity."
            )
    except:
        st.write("Insurance data unavailable")

    try:
        from backend.api.advisor_overrides import apply_overrides
        _current_alloc = allocation if isinstance(allocation, dict) else {}
        allocation = apply_overrides(_current_alloc, client_data)
        
        override_applied = allocation.get("override_applied", False)
        override_reason = allocation.get("override_reason", "")
        if override_applied:
            st.warning(f"Advisor Adjustment: {override_reason}")
    except Exception:
        pass

    st.markdown("---")
    from backend.api.report_generator import generate_full_report
    if st.button("Download Advanced Report"):
        if critical_macro_fallback:
            st.warning(
                "Live market data is stale. Use 'Generate Detailed PDF Report' to confirm report generation with cached data."
            )
        else:
            with st.spinner("Generating report..."):
                try:
                    report_client_data = {
                        **client_data,
                        "monthly_savings": effective_monthly_savings,
                    }
                    pdf_bytes = generate_full_report(report_client_data, {
                        "risk": risk_profile,
                        "allocation": allocation,
                        "insurance": insurance_gap
                    })
                    if pdf_bytes:
                        st.download_button(
                            label="📄 Download PDF Report",
                            data=pdf_bytes,
                            file_name=f"financial_report_{client_data.get('marital_status', 'client').lower()}_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Report generation failed — no output returned.")
                except Exception as e:
                    st.error(f"Report generation error: {e}")
