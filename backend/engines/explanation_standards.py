from config import is_feature_enabled

if is_feature_enabled("v2_risk_explanation", True):
    from backend.engines.v2.explanation_standards import (
        ScoreStandard,
        _STANDARDS,
        get_score_reasoning,
    )
else:
    from backend.engines.v1.explanation_standards import (
        ScoreStandard,
        _STANDARDS,
        get_score_reasoning,
    )
