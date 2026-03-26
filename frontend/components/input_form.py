import streamlit as st


def render_input_form():
    """Renders the client profile and goals input form interactively."""
    st.subheader("Personal Details")
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Current Age", min_value=18, max_value=100, value=30)
        marital_status = st.selectbox("Marital Status", ["Single", "Married"])
    with col2:
        default_dependents = 0 if marital_status == "Single" else 2
        dependents = st.number_input(
            "Dependents", min_value=0, max_value=10, value=default_dependents
        )
        target_retirement_age = st.number_input(
            "Target Retirement Age", min_value=int(age + 1), max_value=100, value=max(60, int(age + 1))
        )

    st.subheader("Financial Details (₹)")
    col3, col4 = st.columns(2)
    with col3:
        monthly_income = st.number_input(
            "Monthly Net Income", min_value=0.0, value=150000.0, step=10000.0
        )
    with col4:
        monthly_savings = st.number_input(
            "Monthly Savings Capacity",
            min_value=0.0,
            max_value=float(monthly_income) if monthly_income > 0 else 100.0,
            value=min(40000.0, float(monthly_income)),
            step=5000.0,
        )

    st.subheader("Existing Portfolio Breakdown (₹)")
    col5, col6 = st.columns(2)
    with col5:
        existing_fd = st.number_input(
            "Fixed Deposits / Bonds", min_value=0.0, value=500000.0, step=50000.0
        )
        existing_savings = st.number_input(
            "Savings Account / Cash", min_value=0.0, value=200000.0, step=50000.0
        )
    with col6:
        existing_gold = st.number_input(
            "Gold Investments", min_value=0.0, value=100000.0, step=50000.0
        )
        existing_mutual_funds = st.number_input(
            "Mutual Funds / Equity", min_value=0.0, value=100000.0, step=50000.0
        )

    st.subheader("Insurance & Liabilities")
    ins_col1, ins_col2, ins_col3 = st.columns(3)
    with ins_col1:
        term_life_cover = st.number_input(
            "Term Life Cover", min_value=0.0, value=1000000.0, step=100000.0
        )
    with ins_col2:
        health_cover = st.number_input(
            "Health Cover", min_value=0.0, value=500000.0, step=100000.0
        )
    with ins_col3:
        annual_insurance_premium = st.number_input(
            "Annual Insurance Premium", min_value=0.0, value=30000.0, step=5000.0
        )

    num_loans = st.number_input(
        "Number of Outstanding Loans", min_value=0, max_value=5, value=0, step=1
    )
    outstanding_loans = []
    for idx in range(int(num_loans)):
        st.markdown(f"**Loan {idx + 1}**")
        loan_col1, loan_col2, loan_col3 = st.columns(3)
        with loan_col1:
            loan_type = st.selectbox(
                f"Loan Type {idx + 1}",
                ["Home", "Car", "Personal", "Education", "Other"],
                key=f"loan_type_{idx}",
            )
        with loan_col2:
            outstanding_principal = st.number_input(
                f"Outstanding Principal {idx + 1}",
                min_value=0.0,
                value=0.0,
                step=100000.0,
                key=f"loan_principal_{idx}",
            )
        with loan_col3:
            emi = st.number_input(
                f"Monthly EMI {idx + 1}",
                min_value=0.0,
                value=0.0,
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
    behavior_traits = st.selectbox(
        "Market Behavior", ["Prefers stability", "Moderate", "High risk"]
    )

    st.subheader("Financial Goals")
    annual_sip_step_up_pct = st.slider(
        "Annual SIP Step-Up %",
        min_value=0,
        max_value=25,
        value=10,
        step=1,
    )
    st.markdown("**Retirement**")
    retirement_expense = st.number_input(
        "Monthly Expense in Retirement (Current Value)",
        min_value=0.0,
        value=50000.0,
        step=5000.0,
    )
    include_post_retirement_income = st.selectbox(
        "Include Post-Retirement Income Planning?",
        ["No", "Yes"],
    )
    post_retirement_income = 0.0
    post_retirement_years = 25
    if include_post_retirement_income == "Yes":
        post_retirement_income = st.number_input(
            "What monthly income do you need after retirement?",
            min_value=0.0,
            value=60000.0,
            step=5000.0,
        )
        post_retirement_years = st.number_input(
            "How many years do you expect to live post-retirement?",
            min_value=1,
            max_value=50,
            value=25,
            step=1,
        )

    st.markdown("**Child Education**")
    education_cost = st.number_input(
        "Present Cost of Education", min_value=0.0, value=2000000.0, step=100000.0
    )
    education_years = st.number_input(
        "Years to Education Goal", min_value=0, max_value=25, value=12
    )

    if monthly_savings > monthly_income:
        st.error("Savings cannot exceed income.")
    elif target_retirement_age <= age:
        st.error("Retirement age must be strictly greater than current age.")
    else:
        total_emi = sum(float(loan.get("emi", 0.0)) for loan in outstanding_loans)
        effective_monthly_savings = max(0.0, monthly_savings - total_emi)
        st.session_state.client_data = {
            "age": age,
            "dependents": dependents,
            "marital_status": marital_status,
            "target_retirement_age": target_retirement_age,
            "monthly_income": monthly_income,
            "monthly_savings": monthly_savings,
            "effective_monthly_savings": effective_monthly_savings,
            "emi_total": total_emi,
            "existing_fd": existing_fd,
            "existing_savings": existing_savings,
            "existing_gold": existing_gold,
            "existing_mutual_funds": existing_mutual_funds,
            "existing_corpus": existing_fd
            + existing_savings
            + existing_gold
            + existing_mutual_funds,  # Computed Total
            "insurance_inputs": {
                "term_life_cover": term_life_cover,
                "health_cover": health_cover,
                "annual_insurance_premium": annual_insurance_premium,
                "outstanding_loans": outstanding_loans,
            },
            "existing_insurance": {"term": term_life_cover, "health": health_cover},
            "behavior": behavior_traits,
            "annual_sip_step_up_pct": float(annual_sip_step_up_pct),
            "goals": {
                "retirement": {
                    "expense": retirement_expense,
                    "include_post_retirement_income": include_post_retirement_income == "Yes",
                    "post_retirement_income": post_retirement_income,
                    "post_retirement_years": int(post_retirement_years),
                    "annual_sip_step_up_pct": float(annual_sip_step_up_pct),
                },
                "education": {
                    "cost": education_cost,
                    "years": education_years,
                    "annual_sip_step_up_pct": float(annual_sip_step_up_pct),
                },
            },
        }
