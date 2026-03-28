from typing import Any, Dict, List

from backend.engines.recommendation_engine.dynamic_recommender import run_dynamic_pipeline


class PortfolioGapAdvisor:
    """Compares current holdings to target allocation and recommends action."""

    _CURRENT_PORTFOLIO_MAP = {
        "fd_bonds": "debt",
        "cash": "debt",
        "equity": "equity",
        "gold": "gold",
        "debt": "debt",
    }
    _DISPLAY_ORDER = ("equity", "debt", "gold")
    _RECOMMENDATION_ALLOCATION_MAP = {
        "equity": {"Equity": 100.0},
        "debt": {"Debt": 100.0},
        "gold": {"Gold": 100.0},
    }

    def __init__(self, tolerance_pct: float = 0.01):
        self.tolerance_pct = max(0.0, float(tolerance_pct))

    @staticmethod
    def _normalize_target_allocation(target_allocation: Dict[str, Any]) -> Dict[str, float]:
        normalized: Dict[str, float] = {}
        for asset_class, raw_value in (target_allocation or {}).items():
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            normalized[str(asset_class).strip().lower()] = value / 100.0 if value > 1.0 else value
        return normalized

    def _normalize_current_portfolio(self, current_portfolio: Dict[str, Any]) -> Dict[str, float]:
        normalized = {"equity": 0.0, "debt": 0.0, "gold": 0.0}
        for raw_asset, raw_value in (current_portfolio or {}).items():
            asset_key = self._CURRENT_PORTFOLIO_MAP.get(str(raw_asset).strip().lower())
            if not asset_key:
                continue
            try:
                normalized[asset_key] = normalized.get(asset_key, 0.0) + float(raw_value)
            except (TypeError, ValueError):
                continue
        return normalized

    def _ordered_asset_classes(self, asset_classes: set[str]) -> List[str]:
        prioritized = [asset for asset in self._DISPLAY_ORDER if asset in asset_classes]
        extras = sorted(asset for asset in asset_classes if asset not in self._DISPLAY_ORDER)
        return prioritized + extras

    def _resolve_action(self, current_pct: float, target_pct: float) -> str:
        gap_pct = target_pct - current_pct
        if current_pct > self.tolerance_pct and target_pct <= self.tolerance_pct:
            return "EXIT"
        if current_pct <= self.tolerance_pct and target_pct > self.tolerance_pct:
            return "ENTER"
        if gap_pct > self.tolerance_pct:
            return "INCREASE"
        if gap_pct < -self.tolerance_pct:
            return "REDUCE"
        return "MAINTAIN"

    @staticmethod
    def _asset_class_from_fund(fund: Dict[str, Any]) -> str | None:
        raw = str(
            fund.get("asset_class")
            or fund.get("category")
            or fund.get("class")
            or ""
        ).strip().lower()
        if not raw:
            return None
        if "gold" in raw or "commodity" in raw:
            return "gold"
        if "debt" in raw or "liquid" in raw or "bond" in raw or "fd" in raw or "cash" in raw:
            return "debt"
        if "equity" in raw or "large cap" in raw or "mid cap" in raw or "small cap" in raw or "flexi" in raw or "hybrid" in raw:
            return "equity"
        return None

    @staticmethod
    def _risk_category(risk_profile: Dict[str, Any] | str) -> str:
        if isinstance(risk_profile, dict):
            return str(risk_profile.get("category") or "Moderate")
        return str(risk_profile or "Moderate")

    @staticmethod
    def _urgency_for_gap(gap_pct: float) -> str:
        abs_gap = abs(float(gap_pct))
        if abs_gap >= 20:
            return "high"
        if abs_gap >= 7.5:
            return "medium"
        return "low"

    @staticmethod
    def _reason_text(action: str, asset_class: str, current_pct: float, target_pct: float, risk_category: str) -> str:
        diff = abs(target_pct - current_pct)
        if action in {"INCREASE", "ENTER"}:
            return (
                f"Your {asset_class} allocation ({current_pct:.0f}%) is {diff:.0f}% below "
                f"your target ({target_pct:.0f}%) given your {risk_category} risk profile."
            )
        if action in {"REDUCE", "EXIT"}:
            return (
                f"Your {asset_class} allocation ({current_pct:.0f}%) is {diff:.0f}% above "
                f"your target ({target_pct:.0f}%) given your {risk_category} risk profile."
            )
        return (
            f"Your {asset_class} allocation is close to target and does not need a major rebalance."
        )

    @staticmethod
    def _missing_fund_message(asset_class: str) -> str:
        return (
            f"No qualifying fund found in current universe for {asset_class}. "
            "Recommend consulting fund master list."
        )

    def _find_primary_underweight(self, gap_list: List[Dict[str, Any]], excluding: str | None = None) -> Dict[str, Any] | None:
        candidates = [
            gap
            for gap in gap_list
            if gap.get("action") in {"INCREASE", "ENTER"}
            and gap.get("asset_class") != excluding
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda gap: float(gap.get("gap_amount", 0.0)))

    def _select_existing_fund_to_reduce(self, existing_funds: List[Dict[str, Any]], asset_class: str) -> Dict[str, Any] | None:
        matches = [
            fund for fund in existing_funds
            if self._asset_class_from_fund(fund) == asset_class
        ]
        if not matches:
            return None
        return max(
            matches,
            key=lambda fund: float(
                fund.get("current_value")
                or fund.get("amount")
                or fund.get("value")
                or fund.get("allocation_amount")
                or 0.0
            ),
        )

    def compute_allocation_gap(
        self,
        current_portfolio: Dict[str, Any],
        target_allocation: Dict[str, Any],
        total_corpus: float,
    ) -> List[Dict[str, Any]]:
        """
        current_portfolio: {"fd_bonds": 500000, "gold": 100000, "cash": 200000, "equity": 100000}
        target_allocation: {"equity": 0.70, "debt": 0.20, "gold": 0.10}
        Returns gaps like:
        [{"asset_class": "equity", "current_pct": 11, "target_pct": 70, "gap_pct": 59, "gap_amount": 531000, "action": "INCREASE"}]
        """
        total = float(total_corpus or 0.0)
        if total <= 0:
            total = sum(float(value or 0.0) for value in (current_portfolio or {}).values())
        if total <= 0:
            return []

        normalized_current = self._normalize_current_portfolio(current_portfolio)
        normalized_target = self._normalize_target_allocation(target_allocation)
        asset_classes = {
            asset_class
            for asset_class in set(normalized_current) | set(normalized_target)
            if normalized_current.get(asset_class, 0.0) > 0 or normalized_target.get(asset_class, 0.0) > 0
        }

        gaps: List[Dict[str, Any]] = []
        for asset_class in self._ordered_asset_classes(asset_classes):
            current_amount = float(normalized_current.get(asset_class, 0.0))
            current_pct = (current_amount / total) * 100.0
            target_pct = float(normalized_target.get(asset_class, 0.0)) * 100.0
            gap_pct = target_pct - current_pct
            gap_amount = (gap_pct / 100.0) * total
            gaps.append(
                {
                    "asset_class": asset_class,
                    "current_pct": round(current_pct, 2),
                    "target_pct": round(target_pct, 2),
                    "gap_pct": round(gap_pct, 2),
                    "gap_amount": round(gap_amount, 2),
                    "action": self._resolve_action(current_pct, target_pct),
                }
            )
        return gaps

    def recommend_funds_for_gap(
        self,
        gap_list: List[Dict[str, Any]],
        risk_profile: Dict[str, Any] | str,
        market_signals: Dict[str, Any],
        existing_funds: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []
        risk_category = self._risk_category(risk_profile)

        for gap in gap_list:
            action = str(gap.get("action", "MAINTAIN")).upper()
            asset_class = str(gap.get("asset_class", "")).lower()
            gap_amount = max(0.0, float(gap.get("gap_amount", 0.0)))
            current_pct = float(gap.get("current_pct", 0.0))
            target_pct = float(gap.get("target_pct", 0.0))
            urgency = self._urgency_for_gap(float(gap.get("gap_pct", 0.0)))

            if action in {"INCREASE", "ENTER"}:
                top_fund = None
                allocation_map = self._RECOMMENDATION_ALLOCATION_MAP.get(asset_class, {})
                if allocation_map:
                    ranked = run_dynamic_pipeline(
                        allocation_weights=allocation_map,
                        risk_profile=risk_category,
                        market_signals=market_signals or {},
                    )
                    if ranked:
                        top_fund = ranked[0]

                fund_name = (
                    str(top_fund.get("name")).strip()
                    if top_fund and top_fund.get("name")
                    else None
                )
                category = top_fund.get("category", asset_class.title()) if top_fund else asset_class.title()
                benchmark_alpha = float(
                    (top_fund or {}).get("alpha_3y", (top_fund or {}).get("alpha_1y", 0.0))
                )
                reason = (
                    self._reason_text(action, asset_class, current_pct, target_pct, risk_category)
                    if fund_name
                    else self._missing_fund_message(asset_class)
                )
                suggestions = {
                    "action": action,
                    "asset_class": asset_class,
                    "fund_name": fund_name,
                    "category": category,
                    "reason": reason,
                    "suggested_sip": round(gap_amount / 12.0, 2),
                    "suggested_lumpsum": round(gap_amount, 2),
                    "urgency": urgency,
                    "benchmark_alpha": round(benchmark_alpha, 2),
                    "replaces": None,
                    "rebalance_note": (
                        f"Deploy ₹{gap_amount:,.0f} over the next 12 months to move {asset_class} closer to target."
                    ),
                }
                recommendations.append(suggestions)
                continue

            if action in {"REDUCE", "EXIT"}:
                fund_to_reduce = self._select_existing_fund_to_reduce(existing_funds, asset_class)
                redeem_amount = abs(float(gap.get("gap_amount", 0.0)))
                underweight = self._find_primary_underweight(gap_list, excluding=asset_class)
                redeploy_asset = underweight.get("asset_class") if underweight else None
                redeploy_amount = min(redeem_amount, abs(float((underweight or {}).get("gap_amount", 0.0))))
                fund_name = (
                    str(fund_to_reduce.get("name")).strip()
                    if fund_to_reduce and fund_to_reduce.get("name")
                    else None
                )
                reason = (
                    self._reason_text(action, asset_class, current_pct, target_pct, risk_category)
                    if fund_name
                    else self._missing_fund_message(asset_class)
                )
                recommendations.append(
                    {
                        "action": action,
                        "asset_class": asset_class,
                        "fund_name": fund_name,
                        "category": fund_to_reduce.get("category", asset_class.title()) if fund_to_reduce else asset_class.title(),
                        "reason": reason,
                        "suggested_sip": 0.0,
                        "suggested_lumpsum": 0.0,
                        "urgency": urgency,
                        "benchmark_alpha": round(
                            float(
                                (fund_to_reduce or {}).get(
                                    "alpha_3y",
                                    (fund_to_reduce or {}).get("alpha_1y", 0.0),
                                )
                        ),
                        2,
                    ),
                        "replaces": fund_name,
                        "rebalance_note": (
                            f"Consider {'exiting' if action == 'EXIT' else 'redeeming'} ₹{redeem_amount:,.0f} "
                            f"from {(fund_name or asset_class)} and redeploying "
                            f"₹{redeploy_amount:,.0f} to {redeploy_asset or 'the underweight allocation'}."
                        ),
                    }
                )
                continue

            recommendations.append(
                {
                    "action": "MAINTAIN",
                    "asset_class": asset_class,
                    "fund_name": None,
                    "category": asset_class.title(),
                    "reason": self._reason_text("MAINTAIN", asset_class, current_pct, target_pct, risk_category),
                    "suggested_sip": 0.0,
                    "suggested_lumpsum": 0.0,
                    "urgency": "low",
                    "benchmark_alpha": 0.0,
                    "replaces": None,
                    "rebalance_note": "No major action needed; current allocation is close to target.",
                }
            )

        return recommendations
