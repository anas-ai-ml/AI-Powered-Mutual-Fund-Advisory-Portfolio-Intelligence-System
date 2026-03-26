from config import is_feature_enabled

if is_feature_enabled("investment_mode_recommendation", True):
    from backend.engines.v2.investment_mode_engine import (
        recommend_investment_mode,
    )
else:
    from backend.funds.investment_mode import (
        get_recommended_strategy as recommend_investment_mode,
    )
