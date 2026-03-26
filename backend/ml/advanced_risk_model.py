import numpy as np
from typing import Dict, Any, Optional
from sklearn.ensemble import RandomForestRegressor


class AdvancedRiskModel:
    def __init__(self):
        # Random Forest gives more stable, non-linear risk capacity mapping
        # from standardized investor profile features.
        self.model = RandomForestRegressor(n_estimators=200, random_state=42)
        self.feature_weights = {
            "age": 0.25,
            "savings_ratio": 0.25,
            "behavior": 0.35,
            "dependents": 0.15,
        }
        self._model_trained = False

    def train(self, df):
        X = df.drop("risk_score", axis=1)
        y = df["risk_score"]
        self.model.fit(X, y)
        self._model_trained = True

    def _encode_behavior(self, behavior: str) -> float:
        # Accept both UI-friendly strings and numeric encodings.
        if isinstance(behavior, (int, float)):
            # Expected numeric mapping: conservative=1, moderate=2, aggressive=3
            return float(max(1.0, min(3.0, behavior)))

        behavior_lower = str(behavior).lower().strip()
        if "aggressive" in behavior_lower or "high" in behavior_lower:
            return 3.0
        elif "moderate" in behavior_lower or "balanced" in behavior_lower:
            return 2.0
        else:
            return 1.0

    def _normalize_age(self, age: int) -> float:
        return max(0, min(70, age)) / 70.0

    def _normalize_savings(self, savings: float, income: float) -> float:
        if income <= 0:
            return 0.0
        return min(savings / income, 1.0)

    def _normalize_dependents(self, dependents: int) -> float:
        return max(0, min(5, dependents)) / 5.0

    def predict(self, user_input: Dict[str, Any], macro_score: float = 0.5) -> float:
        if self._model_trained:
            try:
                features = [
                    user_input.get("age", 30),
                    user_input.get("income", 100000),
                    user_input.get("savings", 10000),
                    self._encode_behavior(user_input.get("behavior", "moderate")),
                    user_input.get("dependents", 0),
                ]
                base_score = self.model.predict([features])[0]
            except:
                base_score = self._rule_based_score(user_input)
        else:
            base_score = self._rule_based_score(user_input)

        macro_weight = 0.15
        adjusted_score = (
            base_score * (1 - macro_weight) + (macro_score * 10) * macro_weight
        )

        return round(max(1.0, min(10.0, adjusted_score)), 2)

    def _rule_based_score(self, user_input: Dict[str, Any]) -> float:
        age = user_input.get("age", 30)
        income = user_input.get("income", 100000)
        savings = user_input.get("savings", 10000)
        behavior = user_input.get("behavior", "moderate")
        dependents = user_input.get("dependents", 0)

        age_norm = self._normalize_age(age)
        savings_norm = self._normalize_savings(savings, income)
        behavior_norm = (self._encode_behavior(behavior) - 1) / 2.0
        dependents_norm = self._normalize_dependents(dependents)

        # Risk capacity typically decreases with age and with more dependents.
        age_capacity_norm = 1.0 - age_norm
        dependents_capacity_norm = 1.0 - dependents_norm

        raw_score = (
            age_capacity_norm * self.feature_weights["age"]
            + savings_norm * self.feature_weights["savings_ratio"]
            + behavior_norm * self.feature_weights["behavior"]
            + dependents_capacity_norm * self.feature_weights["dependents"]
        ) * 10

        return raw_score

    def predict_with_confidence(
        self,
        user_input: Dict[str, Any],
        macro_score: float = 0.5,
        historical_predictions: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        score = self.predict(user_input, macro_score)

        if historical_predictions is not None and len(historical_predictions) > 10:
            std = np.std(historical_predictions)
            confidence = "high" if std < 1.0 else "medium" if std < 2.0 else "low"
        else:
            confidence = "medium"

        return {
            "score": score,
            "confidence": confidence,
            "model_version": "1.0.0",
            "features_used": list(self.feature_weights.keys()),
            "model_trained": self._model_trained,
        }

    def get_feature_importance(self) -> Dict[str, float]:
        return self.feature_weights.copy()


class EnsembleRiskModel:
    def __init__(self):
        self.models = [AdvancedRiskModel(), AdvancedRiskModel(), AdvancedRiskModel()]
        self.weights = [0.4, 0.35, 0.25]

    def predict(self, user_input: Dict[str, Any], macro_score: float = 0.5) -> float:
        predictions = [model.predict(user_input, macro_score) for model in self.models]
        weighted_sum = sum(p * w for p, w in zip(predictions, self.weights))
        return round(weighted_sum, 2)
