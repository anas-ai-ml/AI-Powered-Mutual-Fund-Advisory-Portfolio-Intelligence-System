from config import is_feature_enabled

if is_feature_enabled("v2_risk_explanation", True):
    from backend.engines.v2.risk_engine import (
        calculate_risk_score,
        compute_risk,
        risk_score_to_allocation,
    )
else:
    from backend.engines.v1.risk_engine import (
        calculate_risk_score,
        compute_risk,
        risk_score_to_allocation,
    )
