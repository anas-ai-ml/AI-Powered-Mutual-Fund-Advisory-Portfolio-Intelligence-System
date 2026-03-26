def analyze_insurance_gap(profile, existing, target_corpus=0):
    required_term = max(profile.get("income", 0) * 10, target_corpus)
    term_gap = max(0, required_term - existing.get("term", 0))

    health_required = 500000 if profile.get("age", 0) < 45 else 1000000
    health_gap = max(0, health_required - existing.get("health", 0))

    return {"term_gap": term_gap, "health_gap": health_gap}


def calculate_term_insurance_need(profile, loans=0, existing_corpus=0):
    annual_income = profile.get("income", 0)
    years_to_retirement = profile.get("years_to_retirement", 30)

    human_life_value = annual_income * min(years_to_retirement, 10)

    debt_cover = loans
    corpus_needed = existing_corpus

    required_cover = max(human_life_value, debt_cover + corpus_needed)

    return {
        "recommended_term_cover": round(required_cover, -5),
        "human_life_value": human_life_value,
        "debt_to_cover": debt_cover,
        "corpus_shortfall": max(0, corpus_needed - existing_corpus),
        "optimal_tenure": years_to_retirement + 5,
    }


def calculate_health_insurance_gap(profile, existing_coverage):
    age = profile.get("age", 35)
    family_size = profile.get("family_size", 4)

    base_cover = 500000 if age < 45 else 1000000

    if family_size > 4:
        base_cover *= 1.5

    current = existing_coverage.get("health", 0)

    gap = max(0, base_cover - current)

    return {
        "recommended_health_cover": round(base_cover, -5),
        "current_coverage": current,
        "gap": round(gap, 2),
        "priority": "High" if gap > 500000 else "Medium" if gap > 0 else "Low",
    }


def calculate_critical_illness_need(profile):
    age = profile.get("age", 35)
    income = profile.get("income", 0)

    ci_cover = 1000000 if age < 40 else 2000000

    annual_income_protection = income * 2

    recommended = max(ci_cover, annual_income_protection)

    return {
        "recommended_ci_cover": round(recommended, -5),
        "based_on_age": ci_cover,
        "based_on_income": annual_income_protection,
    }


def generate_insurance_recommendations(profile, existing_insurance):
    recommendations = []

    term_gap = analyze_insurance_gap(profile, existing_insurance)

    if term_gap["term_gap"] > 0:
        recommendations.append(
            {
                "type": "Term Insurance",
                "gap": term_gap["term_gap"],
                "priority": "Critical",
                "action": f"Add term insurance cover of ₹{round(term_gap['term_gap'], -5):,}",
            }
        )

    health_analysis = calculate_health_insurance_gap(profile, existing_insurance)
    if health_analysis["gap"] > 0:
        recommendations.append(
            {
                "type": "Health Insurance",
                "gap": health_analysis["gap"],
                "priority": health_analysis["priority"],
                "action": f"Increase health cover by ₹{round(health_analysis['gap'], -5):,}",
            }
        )

    ci_need = calculate_critical_illness_need(profile)
    existing_ci = existing_insurance.get("critical_illness", 0)
    ci_gap = max(0, ci_need["recommended_ci_cover"] - existing_ci)

    if ci_gap > 0:
        recommendations.append(
            {
                "type": "Critical Illness",
                "gap": ci_gap,
                "priority": "Medium",
                "action": f"Add CI rider or separate cover of ₹{round(ci_gap, -5):,}",
            }
        )

    return recommendations


# === STANDARDIZED ENTRY POINT (AUTO-FIX) ===


def analyze_gap(user_data: dict):
    """
    Safe wrapper for insurance gap analysis
    Works regardless of internal implementation
    """

    try:
        insurance_inputs = user_data.get("insurance_inputs", {})
        annual_income = float(user_data.get("monthly_income", 0.0)) * 12.0
        recommended_term = annual_income * 10.0
        term_cover = float(insurance_inputs.get("term_life_cover", 0.0))
        health_cover = float(insurance_inputs.get("health_cover", 0.0))
        return {
            "life_gap": max(0.0, recommended_term - term_cover),
            "health_gap": max(0.0, 500000.0 - health_cover),
            "recommended_term_cover": recommended_term,
            "current_term_cover": term_cover,
            "current_health_cover": health_cover,
        }

    except Exception as e:
        return {"error": str(e), "life_gap": 0, "health_gap": 0}
