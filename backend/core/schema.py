from typing import Any, Dict, List


REQUIRED_OUTPUT_KEYS = [
    "engine_version",
    "contract_version",
    "status",
    "financial_health",
    "priority_actions",
    "investment_allowed",
    "allocation",
    "confidence_score",
    "stress_test",
    "decision_trace",
]

_PRIORITY_LEVELS = {"CRITICAL", "HIGH", "MEDIUM"}
_TRACE_LEVELS = {"CRITICAL", "HIGH", "MEDIUM", "INFO"}


def _ensure_trace_entry(entry: Any) -> Dict[str, str]:
    if isinstance(entry, dict):
        return {
            "step": str(entry.get("step", "unknown") or "unknown"),
            "message": str(entry.get("message", "") or ""),
            "level": str(entry.get("level", "INFO") or "INFO").upper(),
        }
    return {"step": "unknown", "message": str(entry or ""), "level": "INFO"}


def enforce_types(output: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(output or {})
    normalized["engine_version"] = str(normalized.get("engine_version", "") or "")
    normalized["contract_version"] = str(normalized.get("contract_version", "") or "")
    normalized["status"] = str(normalized.get("status", "") or "")
    normalized["investment_allowed"] = bool(normalized.get("investment_allowed", False))
    normalized["reason"] = str(normalized.get("reason", "") or "")

    financial_health = normalized.get("financial_health")
    if not isinstance(financial_health, dict):
        financial_health = {}
    try:
        financial_health["score"] = float(financial_health.get("score", 0.0) or 0.0)
    except Exception:
        financial_health["score"] = 0.0
    financial_health["band"] = str(financial_health.get("band", "") or "")
    financial_health["drivers"] = financial_health.get("drivers")
    if not isinstance(financial_health["drivers"], list):
        financial_health["drivers"] = []
    normalized["financial_health"] = financial_health

    priority_actions = normalized.get("priority_actions")
    if not isinstance(priority_actions, list):
        priority_actions = []
    normalized["priority_actions"] = [
        {
            "level": str((item or {}).get("level", "") or ""),
            "action": str((item or {}).get("action", "") or ""),
            "reason": str((item or {}).get("reason", "") or ""),
        }
        for item in priority_actions
        if isinstance(item, dict)
    ]

    allocation = normalized.get("allocation")
    if not isinstance(allocation, dict):
        allocation = {"status": "LOCKED"} if allocation == "LOCKED" else {}
    normalized["allocation"] = {str(k): v for k, v in allocation.items()}

    confidence_score = normalized.get("confidence_score")
    normalized["confidence_score"] = confidence_score if isinstance(confidence_score, dict) else {}

    stress_test = normalized.get("stress_test")
    normalized["stress_test"] = stress_test if isinstance(stress_test, dict) else {}

    funds = normalized.get("funds")
    normalized["funds"] = funds if isinstance(funds, list) else []
    normalized["sip"] = str(normalized.get("sip", "") or "")

    trace = normalized.get("decision_trace")
    if not isinstance(trace, list):
        trace = []
    normalized["decision_trace"] = [_ensure_trace_entry(entry) for entry in trace]

    return normalized


def validate_output_schema(output: Dict[str, Any]) -> Dict[str, Any]:
    for key in REQUIRED_OUTPUT_KEYS:
        if key not in output:
            raise ValueError(f"Missing output key: {key}")

    for item in output.get("priority_actions", []):
        if not isinstance(item, dict):
            raise ValueError("Priority action must be a dict")
        for key in ("level", "action", "reason"):
            if key not in item:
                raise ValueError(f"Priority action missing key: {key}")
        if str(item["level"]).upper() not in _PRIORITY_LEVELS:
            raise ValueError(f"Invalid priority action level: {item['level']}")

    for entry in output.get("decision_trace", []):
        if not isinstance(entry, dict):
            raise ValueError("Trace entry must be a dict")
        for key in ("step", "message", "level"):
            if key not in entry:
                raise ValueError(f"Trace entry missing key: {key}")
        if str(entry["level"]).upper() not in _TRACE_LEVELS:
            raise ValueError(f"Invalid trace level: {entry['level']}")

    return output
