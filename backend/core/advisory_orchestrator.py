import json
import time
from typing import Any, Dict, List

from backend.core.config import (
    ADVISORY_CONTRACT_VERSION,
    ADVISORY_ENGINE_VERSION,
    ADVISORY_MODE,
    CONFIDENCE_STRESS_PENALTY,
    STATUS,
)
from backend.core.confidence_engine import compute_confidence
from backend.core.decision_engine import can_invest, get_financial_priority
from backend.core.financial_health import compute_financial_health
from backend.core.guardrails import apply_guardrails
from backend.core.logger import log_event
from backend.core.macro_engine import compute_market_stability
from backend.core.schema import enforce_types, validate_output_schema
from backend.core.stress_engine import run_stress_tests
from backend.core.utils import clamp, safe_round
from backend.core.validation import validate_user_profile


def _fallback_output(message: str) -> Dict[str, Any]:
    return {
        "engine_version": ADVISORY_ENGINE_VERSION,
        "contract_version": ADVISORY_CONTRACT_VERSION,
        "status": STATUS["ERROR"],
        "investment_allowed": False,
        "priority_actions": [],
        "allocation": {"status": "LOCKED"},
        "confidence_score": {},
        "stress_test": {},
        "decision_trace": [
            {"step": "fallback", "message": f"System fallback triggered: {message}", "level": "CRITICAL"}
        ],
        "financial_health": {"score": 0.0, "band": "fragile", "drivers": []},
        "funds": [],
        "sip": "LOCKED",
        "reason": "",
    }


def _finalize_output(output: Dict[str, Any]) -> Dict[str, Any]:
    normalized = enforce_types(output)
    validate_output_schema(normalized)
    return json.loads(json.dumps(normalized))


def _prepare_user_profile(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    profile = validate_user_profile(user_profile)
    profile["geo_risk"] = float(profile.get("geo_risk", 0.5) or 0.5)
    profile["income_stability"] = float(profile.get("income_stability", 0.7) or 0.7)
    profile["vix"] = float(profile.get("vix", 15.0) or 15.0)
    profile["inflation"] = float(profile.get("inflation", 6.0) or 6.0)
    profile["existing_corpus"] = float(profile.get("existing_corpus", 0.0) or 0.0)
    profile["total_liabilities"] = float(profile.get("total_liabilities", 0.0) or 0.0)
    profile["net_worth"] = float(
        profile.get("net_worth", profile["existing_corpus"] - profile["total_liabilities"])
    )
    profile["emi_total"] = float(profile.get("emi_total", 0.0) or 0.0)
    monthly_income = float(profile.get("monthly_income", 0.0) or 0.0)
    profile["emi_ratio"] = float(
        profile.get("emi_ratio", (profile["emi_total"] / monthly_income) if monthly_income > 0 else 0.0)
    )
    monthly_expenses = float(profile.get("monthly_expenses", 0.0) or 0.0)
    liquid_reserves = float(
        profile.get(
            "liquid_reserves",
            profile.get("cash_reserves", profile.get("emergency_corpus", 0.0)),
        )
        or 0.0
    )
    if "emergency_fund_months" not in profile:
        profile["emergency_fund_months"] = (
            liquid_reserves / monthly_expenses if monthly_expenses > 0 else 0.0
        )
    profile["effective_monthly_savings"] = float(
        profile.get("effective_monthly_savings", profile.get("monthly_savings", 0.0))
        or 0.0
    )
    return profile


def run_advisory_pipeline(
    user_profile: Dict[str, Any],
    goals: List[Dict[str, Any]] | None,
    monte_carlo_prob: float,
    allocation_input: Dict[str, Any],
    debug: bool = False,
):
    start = time.perf_counter()
    profile = dict(user_profile or {})
    allocation_seed = dict(allocation_input or {})
    decision_trace: List[Dict[str, str]] = []
    blocks_triggered = 0
    guardrails_applied = 0

    try:
        profile = _prepare_user_profile(profile)

        if float(profile.get("monthly_income", 0.0) or 0.0) == 0:
            decision_trace.append(
                {
                    "step": "sanity_check",
                    "message": "Invalid financial profile: no income detected",
                    "level": "CRITICAL",
                }
            )
            output = {
                "engine_version": ADVISORY_ENGINE_VERSION,
                "contract_version": ADVISORY_CONTRACT_VERSION,
                "status": STATUS["BLOCKED"],
                "financial_health": compute_financial_health(profile, decision_trace),
                "priority_actions": get_financial_priority(profile, decision_trace),
                "investment_allowed": False,
                "allocation": {"status": "LOCKED"},
                "confidence_score": {},
                "stress_test": {},
                "decision_trace": decision_trace[-50:],
                "funds": [],
                "sip": "LOCKED",
                "reason": "Invalid financial profile: no income detected",
            }
            log_event({"event": "block", "reason": output["reason"]})
            return _finalize_output(output)

        financial_health = compute_financial_health(profile, decision_trace)

        if not ADVISORY_MODE:
            output = {
                "engine_version": ADVISORY_ENGINE_VERSION,
                "contract_version": ADVISORY_CONTRACT_VERSION,
                "status": STATUS["LEGACY"],
                "financial_health": financial_health,
                "priority_actions": [],
                "investment_allowed": True,
                "allocation": {k: safe_round(v, 2) for k, v in allocation_seed.items()},
                "confidence_score": {},
                "stress_test": {},
                "decision_trace": decision_trace + [
                    {
                        "step": "mode_switch",
                        "message": "Advisory mode disabled; legacy path used",
                        "level": "INFO",
                    }
                ],
                "funds": [],
                "sip": "",
                "reason": "",
            }
            if debug:
                output["metrics"] = {
                    "execution_time_ms": safe_round((time.perf_counter() - start) * 1000.0, 2),
                    "blocks_triggered": blocks_triggered,
                    "guardrails_applied": guardrails_applied,
                }
            output["decision_trace"] = output["decision_trace"][-50:]
            return _finalize_output(output)

        priority_actions = get_financial_priority(profile, decision_trace)
        allowed, reason = can_invest(profile, decision_trace)

        if not allowed:
            blocks_triggered += 1
            log_event({"event": "block", "reason": reason})
            output = {
                "engine_version": ADVISORY_ENGINE_VERSION,
                "contract_version": ADVISORY_CONTRACT_VERSION,
                "status": STATUS["BLOCKED"],
                "financial_health": financial_health,
                "priority_actions": priority_actions,
                "investment_allowed": False,
                "allocation": {"status": "LOCKED"},
                "confidence_score": {},
                "stress_test": {},
                "decision_trace": decision_trace[-50:],
                "funds": [],
                "sip": "LOCKED",
                "reason": reason,
            }
            if debug:
                output["metrics"] = {
                    "execution_time_ms": safe_round((time.perf_counter() - start) * 1000.0, 2),
                    "blocks_triggered": blocks_triggered,
                    "guardrails_applied": guardrails_applied,
                }
            return _finalize_output(output)

        allocation = apply_guardrails(profile, allocation_seed, decision_trace)
        guardrails_applied = sum(
            1 for item in decision_trace if item.get("step") == "guardrail_application"
        )
        market_stability = compute_market_stability(
            profile["inflation"],
            profile["vix"],
            profile["geo_risk"],
            decision_trace,
        )
        confidence = compute_confidence(
            monte_carlo_prob,
            market_stability,
            profile["income_stability"],
            decision_trace,
        )
        stress = run_stress_tests(profile, goals, allocation, decision_trace)

        market_crash = stress.get("market_crash", {})
        if market_crash.get("severity") == "HIGH":
            confidence["composite_confidence"] = safe_round(
                clamp(
                    float(confidence.get("composite_confidence", 0.0)) * CONFIDENCE_STRESS_PENALTY,
                    0.0,
                    1.0,
                ),
                4,
            )
            confidence["display_confidence_pct"] = safe_round(
                float(confidence["composite_confidence"]) * 100.0, 1
            )
            composite = float(confidence["composite_confidence"])
            confidence["band"] = "high" if composite >= 0.7 else "medium" if composite >= 0.4 else "low"
            decision_trace.append(
                {
                    "step": "confidence_adjustment",
                    "message": "Confidence reduced due to severe market crash stress outcome",
                    "level": "HIGH",
                }
            )

        output = {
            "engine_version": ADVISORY_ENGINE_VERSION,
            "contract_version": ADVISORY_CONTRACT_VERSION,
            "status": STATUS["ACTIVE"],
            "financial_health": financial_health,
            "priority_actions": priority_actions,
            "investment_allowed": True,
            "allocation": allocation,
            "confidence_score": confidence,
            "stress_test": stress,
            "decision_trace": decision_trace[-50:],
            "funds": [],
            "sip": "",
            "reason": "",
        }
        if debug:
            output["metrics"] = {
                "execution_time_ms": safe_round((time.perf_counter() - start) * 1000.0, 2),
                "blocks_triggered": blocks_triggered,
                "guardrails_applied": guardrails_applied,
            }
        return _finalize_output(output)
    except Exception as exc:
        log_event({"event": "fallback", "message": str(exc)})
        return _fallback_output(str(exc))
