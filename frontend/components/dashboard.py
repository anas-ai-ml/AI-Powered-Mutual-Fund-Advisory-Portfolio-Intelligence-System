import streamlit as st
from backend.engines.risk_engine import calculate_risk_score
from backend.engines.goal_engine import (
    calculate_retirement_goal,
    calculate_child_education_goal,
)
from backend.engines.allocation_engine import get_asset_allocation
from backend.engines.monte_carlo_engine import run_monte_carlo_simulation
from backend.engines.portfolio_engine import analyze_portfolio
from backend.engines.projection_engine import generate_projection_table
from backend.engines.recommendation_engine import suggest_mutual_funds
from backend.report.pdf_generator import generate_financial_report
from frontend.components.risk_meter import render_risk_meter
from frontend.components.charts import (
    render_allocation_chart,
    render_projection_chart,
)
from frontend.components.sip_calculator_widget import render_sip_calculator_widget

# ── New Intelligence Layers ───────────────────────────────────────────────────
from backend.engines.intelligence.context_engine import get_macro_context
from backend.processors.explainability import (
    explain_risk_profile,
    explain_all_funds,
    explain_portfolio_health,
)
from backend.processors.output_formatter import (
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


def render_dashboard(client_data: dict):
    # Calculations
    risk_profile = calculate_risk_score(
        age=client_data["age"],
        dependents=client_data["dependents"],
        behavior=client_data["behavior"],
        monthly_income=client_data["monthly_income"],
        monthly_savings=client_data["monthly_savings"],
    )

    # ── NEW: Macro Context Engine ─────────────────────────────────────────────
    macro_context = get_macro_context()

    st.markdown("---")
    st.subheader("Risk Profile Analysis")
    colA, colB = st.columns([1, 2])

    with colA:
        st.metric("Risk Category", risk_profile["category"])
        st.metric("Risk Score", f"{risk_profile['score']} / 10")

    with colB:
        render_risk_meter(risk_profile["score"])

    # ── NEW: Risk Explainability ──────────────────────────────────────────────
    risk_xai = explain_risk_profile(risk_profile, client_data)
    with st.expander("Why is my risk level this?", expanded=False):
        st.markdown(risk_xai["summary"])
        st.markdown("**Key factors that shaped your score:**")
        for factor in risk_xai["key_factors"]:
            st.markdown(f"- {factor}")
        st.info(f"**Recommendation:** {risk_xai['recommendation']}")

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
        mc_col2.metric("Inflation", f"{macro_context['inflation_rate']:.1%}")
        mc_col3.metric(
            "Policy Rate",
            f"{macro_context['interest_rate']:.2%} ({macro_context['interest_rate_trend']})",
        )

    # Portfolio Health
    st.markdown("---")
    st.subheader("Existing Portfolio Health")

    portfolio_analysis = analyze_portfolio(
        existing_fd=client_data["existing_fd"],
        existing_savings=client_data["existing_savings"],
        existing_gold=client_data["existing_gold"],
        existing_mutual_funds=client_data["existing_mutual_funds"],
        risk_score=risk_profile["score"],
        monthly_income=client_data.get("monthly_income", 0.0),
    )

    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        st.metric(
            "Total Existing Corpus",
            f"₹{portfolio_analysis.get('total_corpus', 0.0):,.0f}",
        )
        st.metric(
            "Diversification Score",
            f"{portfolio_analysis['diversification_score']} / 10",
        )
        st.metric(
            "Risk Exposure",
            portfolio_analysis.get("risk_exposure", "N/A (Update Profile)"),
        )

    with col_p2:
        # ── NEW: Portfolio Explainability ─────────────────────────────────────
        portfolio_xai = explain_portfolio_health(portfolio_analysis)
        st.markdown(f"**{portfolio_xai['headline']}**")
        st.markdown(portfolio_xai["narrative"])
        st.write("**Actionable Insights:**")
        for insight in portfolio_analysis["insights"]:
            st.info(insight)

    # Asset Allocation
    allocation = get_asset_allocation(risk_profile["score"])
    st.markdown("---")
    st.subheader("Quantum Asset Allocation")
    render_allocation_chart(allocation["allocation"])

    # ── NEW: Real-Time AI Intelligence Panel ─────────────────────────────────
    st.markdown("---")
    st.subheader("Live Intelligence Panel")

    # Fetch recommendations first so AI layer can score them
    recommended_funds_base, is_live_data = suggest_mutual_funds(
        allocation["allocation"], risk_profile["category"]
    )

    # Invoke the AI layer (uses background cache — no blocking)
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

    # Data freshness badge
    src_badge = {
        "live": ("●", "Live data"),
        "partial": ("◐", "Partial live data"),
        "fallback": ("○", "Offline — using last known values"),
    }.get(data_src, ("○", data_src))
    st.caption(
        f"{src_badge[0]} **{src_badge[1]}** — last refreshed: `{last_upd}` (auto-refreshes every 15 min)"
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
        sig_c4.metric(
            "Global Sentiment",
            signals.get("global_sentiment", "—").capitalize(),
        )
        sig_c5.metric("USD/INR", f"₹{signals.get('usdinr_price', 0):.2f}")

        # —— Row 2: Macro metrics —————————————————————————————
        macro_ind = ai_intel.get("macro_indicators", {})
        m1, m2, m3 = st.columns(3)
        m1.metric(
            "CPI Inflation (YoY)",
            f"{macro_ind.get('cpi_yoy_pct', signals.get('cpi_yoy_pct', 6.0)):.1f}%",
            macro_ind.get("inflation_trend", "").replace("_", " ").capitalize(),
        )
        m2.metric(
            "RBI Repo Rate",
            f"{macro_ind.get('repo_rate_pct', signals.get('repo_rate_pct', 6.5)):.2f}%",
            macro_ind.get("rate_trend", "").capitalize(),
        )
        m3.metric("10Y Bond Yield", f"{macro_ind.get('bond_yield_pct', 7.1):.2f}%")

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

    ret_data = client_data["goals"]["retirement"]
    ret_result = calculate_retirement_goal(
        current_age=client_data["age"],
        current_monthly_expense=ret_data["expense"],
        expected_return_rate=0.13,
        retirement_age=client_data["target_retirement_age"],
        existing_corpus=client_data["existing_corpus"],
    )

    with col1:
        st.markdown(f"#### Retirement ({ret_result['years_to_goal']} Yrs)")
        st.metric("Required Future Corpus", f"₹{ret_result['future_corpus']:,.0f}")
        st.metric("Required Monthly SIP", f"₹{ret_result['required_sip']:,.0f}")

    edu_data = client_data["goals"]["education"]
    edu_result = calculate_child_education_goal(
        edu_data["cost"], edu_data["years"], expected_return_rate=0.13
    )

    with col2:
        st.markdown(f"#### Education ({edu_result['years_to_goal']} Yrs)")
        st.metric("Required Future Corpus", f"₹{edu_result['future_corpus']:,.0f}")
        st.metric("Required Monthly SIP", f"₹{edu_result['required_sip']:,.0f}")

    # Projection Chart
    st.markdown("---")
    st.subheader("Wealth Projection Timeline")
    render_projection_chart(
        client_data["existing_corpus"],
        client_data["monthly_savings"],
        0.13,
        ret_result["years_to_goal"],
    )

    # Monte Carlo Simulation
    st.markdown("---")
    st.subheader("Monte Carlo Simulation")
    st.caption(
        "Testing 1,000 market scenarios to predict Retirement success probability."
    )

    probability = run_monte_carlo_simulation(
        initial_corpus=client_data["existing_corpus"],
        monthly_sip=client_data["monthly_savings"],
        years=ret_result["years_to_goal"],
        target_corpus=ret_result["future_corpus"],
        expected_annual_return=0.13,
        annual_volatility=0.15,
    )

    # ── NEW: Confidence Band Badge ─────────────────────────────────────────────
    mc_fmt = format_monte_carlo_summary(probability, macro_context)
    band = get_confidence_band(probability / 100.0)
    conf_adj = macro_context.get("adjusted_confidence", 0.85)
    band_adj = get_confidence_band(conf_adj)
    cb_col1, cb_col2 = st.columns(2)
    cb_col1.metric(
        "Goal Confidence Band",
        f"{band['icon']} {band['label']} ({probability:.0f}%)",
        help="High = 80-100%, Medium = 50-80%, Low = <50%",
    )
    cb_col2.metric(
        "Macro-Adjusted Confidence",
        f"{band_adj['icon']} {band_adj['label']} ({conf_adj:.0%})",
        help="Confidence adjusted for current inflation, geopolitical risk, and market volatility.",
    )

    st.progress(probability / 100.0)
    st.caption(mc_fmt["simple"])

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
    st.subheader("Investment Scenarios")
    st.caption(
        "How your wealth could grow under different market conditions over your investment horizon."
    )
    scenarios = build_scenario_projections(
        existing_corpus=client_data["existing_corpus"],
        monthly_sip=client_data["monthly_savings"],
        years=ret_result["years_to_goal"],
    )
    sc_cols = st.columns(3)
    for i, sc in enumerate(scenarios):
        with sc_cols[i]:
            st.metric(
                f"{sc['scenario']}",
                f"₹{sc['final_corpus']:,.0f}",
                f"at {sc['annual_return']} p.a.",
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
    render_sip_calculator_widget()

    # Generate PDF Report
    st.markdown("---")
    st.subheader("Client Investment Proposal")

    if st.button("Generate Detailed PDF Report"):
        with st.spinner("Generating proposal..."):
            # Module 5: Prepare SIP Projections (5, 10, 20 Years) at 12%
            sip_amount = client_data["monthly_savings"]
            initial = client_data["existing_corpus"]

            sip_projections = {}
            for y in [5, 10, 20]:
                df = generate_projection_table(initial, sip_amount, 0.12, y)
                sip_projections[f"{y} Years"] = df.iloc[-1]["total_value"]

            # Module 5: Prepare Expected Returns Scenarios
            # Using the retirement timeframe for this module's requirement
            years = ret_result["years_to_goal"]
            expected_returns = {
                "Conservative (8%)": generate_projection_table(
                    initial, sip_amount, 0.08, years
                ).iloc[-1]["total_value"],
                "Moderate (12%)": generate_projection_table(
                    initial, sip_amount, 0.12, years
                ).iloc[-1]["total_value"],
                "Aggressive (15%)": generate_projection_table(
                    initial, sip_amount, 0.15, years
                ).iloc[-1]["total_value"],
            }

            pdf_path = generate_financial_report(
                client_data=client_data,
                risk_data=risk_profile,
                retirement_data=ret_result,
                education_data=edu_result,
                allocation_data=allocation,
                portfolio_data=portfolio_analysis,
                recommended_funds=recommended_funds,
                monte_carlo_prob=probability,
                sip_projections=sip_projections,
                expected_returns=expected_returns,
                ai_intel=ai_intel,
                macro_context=macro_context,
            )
            with open(pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                st.download_button(
                    label="Download Investment Proposal (PDF)",
                    data=pdf_bytes,
                    file_name="Investment_Proposal.pdf",
                    mime="application/pdf",
                )
