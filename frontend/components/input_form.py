import streamlit as st

from backend.engines.goal_engine import GOAL_CONFIGS, GoalType


GOAL_TYPE_NAMES = [goal_type.name for goal_type in GoalType]


def _goal_label_from_name(goal_type_name: str) -> str:
    normalized = GoalType[goal_type_name].value
    config = GOAL_CONFIGS.get(normalized)
    return config.label if config else normalized.replace("_", " ").title()


def _normalize_goal_type_name(goal_type: str | None) -> str:
    if not goal_type:
        return GoalType.RETIREMENT.name
    cleaned = str(goal_type).strip()
    if cleaned in GoalType.__members__:
        return cleaned
    lowered = cleaned.lower()
    for goal_enum in GoalType:
        if goal_enum.value == lowered:
            return goal_enum.name
    return GoalType.CUSTOM.name


def _default_goal_inputs(goal_type_name: str, initial_data: dict) -> dict:
    target_retirement_age = int(
        initial_data.get("target_retirement_age", max(60, int(initial_data.get("age", 30)) + 1))
    )
    monthly_income = float(initial_data.get("monthly_income", 150000.0))
    monthly_savings = float(initial_data.get("monthly_savings", 40000.0))
    implied_monthly_expenses = max(0.0, monthly_income - monthly_savings)

    defaults = {
        GoalType.RETIREMENT.name: {
            "current_monthly_expense": 50000.0,
            "retirement_age": target_retirement_age,
            "include_post_retirement_income": False,
            "post_retirement_income": 60000.0,
            "post_retirement_years": 25,
        },
        GoalType.CHILD_EDUCATION.name: {"target_amount": 2000000.0, "years_to_goal": 12},
        GoalType.CHILD_MARRIAGE.name: {"target_amount": 2500000.0, "years_to_goal": 15},
        GoalType.HOUSE_PURCHASE.name: {"target_amount": 5000000.0, "years_to_goal": 10},
        GoalType.VEHICLE_PURCHASE.name: {"target_amount": 1200000.0, "years_to_goal": 5},
        GoalType.VACATION.name: {"target_amount": 500000.0, "years_to_goal": 3},
        GoalType.WEALTH_CREATION.name: {"target_amount": 10000000.0, "years_to_goal": 15},
        GoalType.EMERGENCY_FUND.name: {
            "monthly_expenses": implied_monthly_expenses or 60000.0,
            "months_of_coverage": 6,
        },
        GoalType.CUSTOM.name: {
            "goal_name": "Custom Goal",
            "target_amount": 1000000.0,
            "years_to_goal": 8,
            "custom_inflation": 0.065,
        },
    }
    return dict(defaults.get(goal_type_name, defaults[GoalType.CUSTOM.name]))


def _normalize_goal_entries(initial_data: dict) -> list[dict]:
    raw_goals = initial_data.get("goals", [])
    normalized: list[dict] = []

    if isinstance(raw_goals, list):
        for goal in raw_goals:
            if not isinstance(goal, dict):
                continue
            goal_type_name = _normalize_goal_type_name(
                goal.get("type") or goal.get("goal_type")
            )
            goal_inputs = dict(goal.get("inputs") or {})
            if not goal_inputs:
                goal_inputs = _default_goal_inputs(goal_type_name, initial_data)
            normalized.append({"type": goal_type_name, "inputs": goal_inputs})
    elif isinstance(raw_goals, dict):
        retirement_goal = raw_goals.get("retirement")
        if retirement_goal:
            normalized.append(
                {
                    "type": GoalType.RETIREMENT.name,
                    "inputs": {
                        "current_monthly_expense": float(retirement_goal.get("expense", 50000.0)),
                        "retirement_age": int(
                            initial_data.get(
                                "target_retirement_age",
                                max(60, int(initial_data.get("age", 30)) + 1),
                            )
                        ),
                        "include_post_retirement_income": bool(
                            retirement_goal.get("include_post_retirement_income", False)
                        ),
                        "post_retirement_income": float(
                            retirement_goal.get("post_retirement_income", 60000.0)
                        ),
                        "post_retirement_years": int(
                            retirement_goal.get("post_retirement_years", 25)
                        ),
                    },
                }
            )
        education_goal = raw_goals.get("education")
        if education_goal:
            normalized.append(
                {
                    "type": GoalType.CHILD_EDUCATION.name,
                    "inputs": {
                        "target_amount": float(education_goal.get("cost", 2000000.0)),
                        "years_to_goal": int(education_goal.get("years", 12)),
                    },
                }
            )

    if normalized:
        return normalized

    return [
        {"type": GoalType.RETIREMENT.name, "inputs": _default_goal_inputs(GoalType.RETIREMENT.name, initial_data)},
        {
            "type": GoalType.CHILD_EDUCATION.name,
            "inputs": _default_goal_inputs(GoalType.CHILD_EDUCATION.name, initial_data),
        },
    ]


def _render_goal_inputs(
    idx: int,
    goal_type_name: str,
    existing_inputs: dict,
    age: int,
    target_retirement_age: int,
) -> dict:
    inputs = {**_default_goal_inputs(goal_type_name, {"age": age, "target_retirement_age": target_retirement_age}), **existing_inputs}
    normalized_goal_type = GoalType[goal_type_name].value
    config = GOAL_CONFIGS.get(normalized_goal_type)
    if config and config.description:
        st.caption(config.description)

    rendered: dict = {}
    if goal_type_name == GoalType.RETIREMENT.name:
        col1, col2 = st.columns(2)
        with col1:
            rendered["current_monthly_expense"] = st.number_input(
                f"Current Monthly Expense #{idx + 1}",
                min_value=0.0,
                value=float(inputs.get("current_monthly_expense", 50000.0)),
                step=5000.0,
                key=f"goal_{idx}_current_monthly_expense",
            )
        with col2:
            # Clamp stored value to be strictly > age to avoid Streamlit crash
            ret_age_min = int(age + 1)
            ret_age_val = max(ret_age_min, int(inputs.get("retirement_age", target_retirement_age)))
            rendered["retirement_age"] = int(
                st.number_input(
                    f"Retirement Age #{idx + 1}",
                    min_value=ret_age_min,
                    max_value=100,
                    value=ret_age_val,
                    step=1,
                    key=f"goal_{idx}_retirement_age",
                )
            )
        include_income = st.selectbox(
            f"Include Post-Retirement Income Planning? #{idx + 1}",
            ["No", "Yes"],
            index=1 if inputs.get("include_post_retirement_income", False) else 0,
            key=f"goal_{idx}_include_post_retirement_income",
        )
        rendered["include_post_retirement_income"] = include_income == "Yes"
        if rendered["include_post_retirement_income"]:
            income_col1, income_col2 = st.columns(2)
            with income_col1:
                rendered["post_retirement_income"] = st.number_input(
                    f"Post-Retirement Monthly Income Needed #{idx + 1}",
                    min_value=0.0,
                    value=float(inputs.get("post_retirement_income", 60000.0)),
                    step=5000.0,
                    key=f"goal_{idx}_post_retirement_income",
                )
            with income_col2:
                rendered["post_retirement_years"] = int(
                    st.number_input(
                        f"Post-Retirement Years #{idx + 1}",
                        min_value=1,
                        max_value=50,
                        value=int(inputs.get("post_retirement_years", 25)),
                        step=1,
                        key=f"goal_{idx}_post_retirement_years",
                    )
                )
        else:
            rendered["post_retirement_income"] = float(inputs.get("post_retirement_income", 0.0))
            rendered["post_retirement_years"] = int(inputs.get("post_retirement_years", 25))
        return rendered

    if goal_type_name == GoalType.EMERGENCY_FUND.name:
        col1, col2 = st.columns(2)
        with col1:
            rendered["monthly_expenses"] = st.number_input(
                f"Monthly Expenses #{idx + 1}",
                min_value=0.0,
                value=float(inputs.get("monthly_expenses", 60000.0)),
                step=5000.0,
                key=f"goal_{idx}_monthly_expenses",
            )
        with col2:
            rendered["months_of_coverage"] = int(
                st.number_input(
                    f"Months of Coverage #{idx + 1}",
                    min_value=1,
                    max_value=24,
                    value=int(inputs.get("months_of_coverage", 6)),
                    step=1,
                    key=f"goal_{idx}_months_of_coverage",
                )
            )
        return rendered

    if goal_type_name == GoalType.CUSTOM.name:
        rendered["goal_name"] = st.text_input(
            f"Custom Goal Name #{idx + 1}",
            value=str(inputs.get("goal_name", "Custom Goal")),
            key=f"goal_{idx}_goal_name",
        )

    amount_label = "Present Cost / Target Amount"
    if goal_type_name == GoalType.HOUSE_PURCHASE.name:
        amount_label = "Property Value Target"
    elif goal_type_name == GoalType.VEHICLE_PURCHASE.name:
        amount_label = "Vehicle Cost Target"
    elif goal_type_name == GoalType.WEALTH_CREATION.name:
        amount_label = "Target Corpus"

    col1, col2 = st.columns(2)
    with col1:
        rendered["target_amount"] = st.number_input(
            f"{amount_label} #{idx + 1}",
            min_value=0.0,
            value=float(inputs.get("target_amount", 1000000.0)),
            step=50000.0,
            key=f"goal_{idx}_target_amount",
        )
    with col2:
        rendered["years_to_goal"] = int(
            st.number_input(
                f"Years to Goal #{idx + 1}",
                min_value=1,          # BUG FIX: was 0 — 0 years produces SIP=0 silently
                max_value=40,
                value=max(1, int(inputs.get("years_to_goal", 10))),
                step=1,
                key=f"goal_{idx}_years_to_goal",
            )
        )

    if goal_type_name == GoalType.CUSTOM.name:
        custom_inflation_pct = st.number_input(
            f"Custom Inflation Rate (%) #{idx + 1}",
            min_value=0.0,
            max_value=25.0,
            value=float(inputs.get("custom_inflation", 0.065) or 0.065) * 100.0,
            step=0.5,
            key=f"goal_{idx}_custom_inflation",
        )
        # BUG FIX: was returning None for 0% — engine expects a float
        rendered["custom_inflation"] = custom_inflation_pct / 100.0 if custom_inflation_pct > 0 else 0.065

    return rendered


def render_input_form(initial_data: dict | None = None) -> dict | None:
    """Render the client profile form and return saved payload on submit."""
    initial_data = initial_data or {}
    goal_entries_default = _normalize_goal_entries(initial_data)
    insurance_inputs = initial_data.get("insurance_inputs", {})
    outstanding_loans_default = insurance_inputs.get("outstanding_loans", [])

    # ── Dynamic counts OUTSIDE the form so changing them re-renders fields ───
    # These live outside st.form so Streamlit reruns immediately on change.
    count_col1, count_col2 = st.columns(2)
    with count_col1:
        goal_entry_count = int(st.number_input(
            "Number of Financial Goals",
            min_value=1,
            max_value=8,
            value=st.session_state.get("if_goal_count", max(1, len(goal_entries_default))),
            step=1,
            key="if_goal_count",
            help="Change this to add or remove goal entries. Fields update immediately.",
        ))
    with count_col2:
        num_loans = int(st.number_input(
            "Number of Outstanding Loans",
            min_value=0,
            max_value=5,
            value=st.session_state.get("if_loan_count", len(outstanding_loans_default)),
            step=1,
            key="if_loan_count",
            help="Change this to add or remove loan fields. Fields update immediately.",
        ))

    # ── Main profile form ─────────────────────────────────────────────────────
    with st.form("client_profile_form", clear_on_submit=False):
        st.subheader("Personal Details")
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input(
                "Current Age",
                min_value=18,
                max_value=100,
                value=int(initial_data.get("age", 30)),
            )
            marital_status = st.selectbox(
                "Marital Status",
                ["Single", "Married"],
                index=0 if initial_data.get("marital_status", "Single") == "Single" else 1,
            )
            occupation = st.text_input(
                "Occupation",
                value=str(initial_data.get("occupation") or ""),
                placeholder="e.g. Salaried, Business Owner, Retired",
            )
        with col2:
            default_dependents = 0 if initial_data.get("marital_status", "Single") == "Single" else 2
            dependents = st.number_input(
                "Dependents",
                min_value=0,
                max_value=10,
                value=int(initial_data.get("dependents", default_dependents)),
            )
            # BUG FIX: clamp stored value so it's always >= age+1 to avoid Streamlit crash
            ret_age_min = int(age + 1)
            ret_age_default = max(
                ret_age_min,
                int(initial_data.get("target_retirement_age", max(60, ret_age_min)))
            )
            target_retirement_age = st.number_input(
                "Target Retirement Age",
                min_value=ret_age_min,
                max_value=100,
                value=ret_age_default,
            )
            income_bracket = st.selectbox(
                "Income Bracket",
                ["", "Below ₹3L", "₹3L–₹7L", "₹7L–₹15L", "₹15L–₹30L", "Above ₹30L"],
                index=0,
                help="Annual income bracket for risk profiling context.",
            )

        st.subheader("Financial Details (₹)")
        col3, col4 = st.columns(2)
        with col3:
            monthly_income = st.number_input(
                "Monthly Net Income",
                min_value=0.0,
                value=float(initial_data.get("monthly_income", 150000.0)),
                step=10000.0,
            )
        with col4:
            # BUG FIX: fallback max was 100.0 — use a large ceiling instead
            savings_max = float(monthly_income) if monthly_income > 0 else 10000000.0
            monthly_savings = st.number_input(
                "Monthly Savings Capacity",
                min_value=0.0,
                max_value=savings_max,
                value=min(
                    float(initial_data.get("monthly_savings", 40000.0)),
                    savings_max,
                ),
                step=5000.0,
            )

        st.subheader("Existing Portfolio Breakdown (₹)")
        col5, col6 = st.columns(2)
        with col5:
            existing_fd = st.number_input(
                "Fixed Deposits / Bonds",
                min_value=0.0,
                value=float(initial_data.get("existing_fd", 500000.0)),
                step=50000.0,
            )
            existing_savings = st.number_input(
                "Savings Account / Cash",
                min_value=0.0,
                value=float(initial_data.get("existing_savings", 200000.0)),
                step=50000.0,
            )
        with col6:
            existing_gold = st.number_input(
                "Gold Investments",
                min_value=0.0,
                value=float(initial_data.get("existing_gold", 100000.0)),
                step=50000.0,
            )
            existing_mutual_funds = st.number_input(
                "Mutual Funds / Equity",
                min_value=0.0,
                value=float(initial_data.get("existing_mutual_funds", 100000.0)),
                step=50000.0,
            )

        st.subheader("Insurance & Liabilities")
        ins_col1, ins_col2, ins_col3 = st.columns(3)
        with ins_col1:
            term_life_cover = st.number_input(
                "Term Life Cover",
                min_value=0.0,
                value=float(insurance_inputs.get("term_life_cover", 1000000.0)),
                step=100000.0,
            )
        with ins_col2:
            health_cover = st.number_input(
                "Health Cover",
                min_value=0.0,
                value=float(insurance_inputs.get("health_cover", 500000.0)),
                step=100000.0,
            )
        with ins_col3:
            annual_insurance_premium = st.number_input(
                "Annual Insurance Premium",
                min_value=0.0,
                value=float(insurance_inputs.get("annual_insurance_premium", 30000.0)),
                step=5000.0,
            )

        # Loan fields — count driven by num_loans set outside the form
        outstanding_loans = []
        if num_loans > 0:
            st.markdown(f"**Outstanding Loans ({num_loans})**")
        loan_type_options = ["Home", "Car", "Personal", "Education", "Other"]
        for idx in range(num_loans):
            existing_loan = (
                outstanding_loans_default[idx]
                if idx < len(outstanding_loans_default)
                else {}
            )
            st.markdown(f"**Loan {idx + 1}**")
            loan_col1, loan_col2, loan_col3 = st.columns(3)
            with loan_col1:
                existing_type = existing_loan.get("type", "Home")
                loan_type = st.selectbox(
                    f"Loan Type {idx + 1}",
                    loan_type_options,
                    index=loan_type_options.index(existing_type)
                    if existing_type in loan_type_options
                    else 0,
                    key=f"loan_type_{idx}",
                )
            with loan_col2:
                outstanding_principal = st.number_input(
                    f"Outstanding Principal {idx + 1}",
                    min_value=0.0,
                    value=float(existing_loan.get("outstanding_principal", 0.0)),
                    step=100000.0,
                    key=f"loan_principal_{idx}",
                )
            with loan_col3:
                emi = st.number_input(
                    f"Monthly EMI {idx + 1}",
                    min_value=0.0,
                    value=float(existing_loan.get("emi", 0.0)),
                    step=5000.0,
                    key=f"loan_emi_{idx}",
                )
            outstanding_loans.append(
                {
                    "type": loan_type,
                    "outstanding_principal": outstanding_principal,
                    "emi": emi,
                }
            )

        st.subheader("Behavioral Traits")
        behavior_options = ["Prefers stability", "Moderate", "High risk"]
        existing_behavior = initial_data.get("behavior", "Moderate")
        behavior_traits = st.selectbox(
            "Market Behavior",
            behavior_options,
            index=behavior_options.index(existing_behavior)
            if existing_behavior in behavior_options
            else 1,
        )

        st.subheader("Financial Goals")
        annual_sip_step_up_pct = st.slider(
            "Annual SIP Step-Up %",
            min_value=0,
            max_value=25,
            value=int(initial_data.get("annual_sip_step_up_pct", 10)),
            step=1,
        )

        # Goal fields — count driven by goal_entry_count set outside the form
        goal_entries = []
        for idx in range(goal_entry_count):
            default_entry = (
                goal_entries_default[idx]
                if idx < len(goal_entries_default)
                else {
                    "type": GoalType.CUSTOM.name,
                    "inputs": _default_goal_inputs(GoalType.CUSTOM.name, initial_data),
                }
            )
            st.markdown(f"**Goal {idx + 1}**")
            goal_type_name = st.selectbox(
                f"Goal Type #{idx + 1}",
                GOAL_TYPE_NAMES,
                index=GOAL_TYPE_NAMES.index(default_entry["type"])
                if default_entry["type"] in GOAL_TYPE_NAMES
                else 0,
                format_func=_goal_label_from_name,
                key=f"goal_type_{idx}",
            )
            goal_inputs = _render_goal_inputs(
                idx=idx,
                goal_type_name=goal_type_name,
                existing_inputs=default_entry.get("inputs", {}),
                age=int(age),
                target_retirement_age=int(target_retirement_age),
            )
            goal_entries.append({"type": goal_type_name, "inputs": goal_inputs})

        submitted = st.form_submit_button("Save Client Profile", width="stretch")

    if not submitted:
        return None

    # ── Post-submit validations ───────────────────────────────────────────────
    if monthly_savings > monthly_income:
        st.error("Monthly savings cannot exceed monthly income.")
        return None

    total_emi = sum(float(loan.get("emi", 0.0)) for loan in outstanding_loans)

    # BUG FIX: warn if EMI burden exceeds savings capacity
    effective_monthly_savings = monthly_savings - total_emi
    if effective_monthly_savings < 0:
        st.warning(
            f"Total EMI (₹{total_emi:,.0f}) exceeds savings capacity (₹{monthly_savings:,.0f}). "
            f"Effective investable surplus is ₹0. Consider reviewing liabilities."
        )
        effective_monthly_savings = 0.0

    for goal_entry in goal_entries:
        if goal_entry["type"] == GoalType.RETIREMENT.name:
            retirement_age = int(goal_entry["inputs"].get("retirement_age", target_retirement_age))
            if retirement_age <= age:
                st.error("Retirement age must be strictly greater than current age.")
                return None

    first_retirement_goal = next(
        (g for g in goal_entries if g["type"] == GoalType.RETIREMENT.name),
        None,
    )

    return {
        "age": age,
        "dependents": dependents,
        "marital_status": marital_status,
        "occupation": occupation.strip() or None,
        "income_bracket": income_bracket or None,
        "target_retirement_age": int(
            first_retirement_goal["inputs"].get("retirement_age", target_retirement_age)
        )
        if first_retirement_goal
        else int(target_retirement_age),
        "monthly_income": monthly_income,
        "monthly_savings": monthly_savings,
        "effective_monthly_savings": effective_monthly_savings,
        "emi_total": total_emi,
        "existing_fd": existing_fd,
        "existing_savings": existing_savings,
        "existing_gold": existing_gold,
        "existing_mutual_funds": existing_mutual_funds,
        "existing_corpus": existing_fd + existing_savings + existing_gold + existing_mutual_funds,
        "insurance_inputs": {
            "term_life_cover": term_life_cover,
            "health_cover": health_cover,
            "annual_insurance_premium": annual_insurance_premium,
            "outstanding_loans": outstanding_loans,
        },
        "existing_insurance": {"term": term_life_cover, "health": health_cover},
        "behavior": behavior_traits,
        "annual_sip_step_up_pct": float(annual_sip_step_up_pct),
        "goals": goal_entries,
    }
