from typing import Dict, Any
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import logging

# We will generate synthetic data once to train the ML risk model
def generate_synthetic_data(n=1000):
    np.random.seed(42)
    ages = np.random.randint(20, 70, n)
    dependents = np.random.randint(0, 5, n)
    # Savings ratio variables
    incomes = np.random.uniform(30000, 500000, n)
    savings_ratios = np.random.uniform(0.01, 0.6, n)
    
    # Behavior encoding (1: conservative, 2: moderate, 3: aggressive)
    behaviors = np.random.choice([1, 2, 3], n)
    
    X = np.column_stack((ages, dependents, behaviors, savings_ratios))
    
    # Intrinsic true score formula (0-10) purely for generating training data baseline
    # Younger = higher risk, more dependents = lower risk, higher savings = higher risk
    age_score = np.interp(ages, [20, 70], [9, 2])
    dep_score = np.interp(dependents, [0, 5], [9, 2])
    sav_score = np.interp(savings_ratios, [0, 0.5], [3, 9])
    bhv_score = np.interp(behaviors, [1, 3], [3, 9])
    
    y = (age_score * 0.25) + (dep_score * 0.15) + (sav_score * 0.25) + (bhv_score * 0.35)
    
    # Add real-world noise variance to require the model to learn
    y += np.random.normal(0, 0.8, n)
    y = np.clip(y, 1.0, 10.0)
    
    return X, y

def train_risk_model():
    X, y = generate_synthetic_data(2000)
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('rf', RandomForestRegressor(n_estimators=50, max_depth=6, random_state=42))
    ])
    pipeline.fit(X, y)
    return pipeline

# Train model on module load (typically takes <50ms for 2000 rows)
logging.info("Training ML Risk Model on synthetic client dataset...")
_risk_model = train_risk_model()

def calculate_risk_score(
    age: int,
    dependents: int,
    behavior: str,
    monthly_income: float,
    monthly_savings: float,
) -> Dict[str, Any]:
    """
    Computes risk score predicting via Random Forest ML model.
    """
    # Parse behavior text to numerical
    behavior_lower = behavior.lower()
    if "high" in behavior_lower or "aggressive" in behavior_lower:
        beh_num = 3
    elif "moderate" in behavior_lower:
        beh_num = 2
    else:
        beh_num = 1
        
    savings_ratio = monthly_savings / monthly_income if monthly_income > 0 else 0.0
    
    # Predict using the trained Random Forest model
    X_input = np.array([[age, dependents, beh_num, savings_ratio]])
    score_pred = _risk_model.predict(X_input)[0]
    score = round(float(np.clip(score_pred, 1.0, 10.0)), 2)
    
    if score < 5:
        category = "Conservative"
    elif 5 <= score <= 7.5:
        category = "Moderate"
    else:
        category = "Aggressive"
    
    return {
        "score": score,
        "category": f"{category} (ML Pred)",
        "explanation": {
            "model_used": "RandomForestRegressor",
            "features": {
                "age_input": age,
                "dependents": dependents,
                "savings_ratio": round(savings_ratio, 2),
                "behavior_encoded": beh_num
            },
            "total_score": score
        }
    }

if __name__ == "__main__":
    test_score = calculate_risk_score(30, 0, "High", 100000, 40000)
    print("Test Profile (Young, 0 Dep, Aggressive, 40% Savings):", test_score)
    
    test_score2 = calculate_risk_score(55, 3, "Conservative", 100000, 10000)
    print("Test Profile (Old, 3 Dep, Conservative, 10% Savings):", test_score2)
