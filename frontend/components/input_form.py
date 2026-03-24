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

    st.subheader("Behavioral Traits")
    behavior_traits = st.selectbox(
        "Market Behavior", ["Prefers stability", "Moderate", "High risk"]
    )

    st.subheader("Financial Goals")
    st.markdown("**Retirement**")
    retirement_expense = st.number_input(
        "Monthly Expense in Retirement (Current Value)",
        min_value=0.0,
        value=50000.0,
        step=5000.0,
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
        st.session_state.client_data = {
            "age": age,
            "dependents": dependents,
            "marital_status": marital_status,
            "target_retirement_age": target_retirement_age,
            "monthly_income": monthly_income,
            "monthly_savings": monthly_savings,
            "existing_fd": existing_fd,
            "existing_savings": existing_savings,
            "existing_gold": existing_gold,
            "existing_mutual_funds": existing_mutual_funds,
            "existing_corpus": existing_fd
            + existing_savings
            + existing_gold
            + existing_mutual_funds,  # Computed Total
            "behavior": behavior_traits,
            "goals": {
                "retirement": {"expense": retirement_expense},
                "education": {"cost": education_cost, "years": education_years},
            },
        }
