import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.api.report_generator import generate_full_report

# Mock data
client_data = {
    "age": 45,
    "dependents": 0,
    "monthly_income": 150000,
    "monthly_savings": 50000,
    "behavior": "Aggressive",
    "total_liabilities": 2000000,
    "existing_insurance": {
        "term": 5000000,
        "health": 300000
    }
}

analysis_data = {
    "risk": {
        "score": 7.5,
        "category": "Aggressive",
        "explanation": {
            "Age": 2.0, "Dependents": 1.5, "Income": 2.5, "Behavior": 1.5
        }
    },
    "goals": [
        {
            "name": "Retirement",
            "years_to_goal": 15,
            "future_corpus": 15000000,
            "required_sip": 35000,
            "return_pct": 12.0
        }
    ],
    "portfolio": {
        "total_corpus": 1200000,
        "diversification_score": 6.5
    },
    "macro": {
        "stability_score": 0.85,
        "ai_market_score": 88
    },
    "funds": [
        {"name": "HDFC Index Nifty 50", "ai_score": 92, "weight": 40, "alpha": 0.5},
        {"name": "Parag Parikh Flexi Cap", "ai_score": 89, "weight": 30, "alpha": 3.2}
    ],
    "monte_carlo": {
        "success_probability": 82.0
    }
}

try:
    print("Generating report...")
    result = generate_full_report(client_data, analysis_data)
    print(f"Success! PDF generated at: {result['pdf_path']}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
