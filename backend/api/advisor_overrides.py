"""
backend/api/advisor_overrides.py
─────────────────────────────────
Advisor override helpers.

- `apply_overrides(allocation, user_data)` — rule-based guardrail logic used
  by the allocation pipeline.
- `AdvisorOverrideAPI` — thin wrapper around the SQLAlchemy session for use
  inside FastAPI request handlers (pass `db` explicitly).

The legacy Flask Blueprint is kept for backward compatibility but now delegates
all storage to the DB via `AdvisorOverrideAPI`.
"""

try:
    from flask import Blueprint, request, jsonify

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from datetime import datetime
from typing import Any, Dict, Optional

if FLASK_AVAILABLE:
    advisor_bp = Blueprint("advisor", __name__)

    # Flask routes are thin stubs; real persistence is via FastAPI + SQLAlchemy.
    @advisor_bp.route("/override", methods=["POST"])
    def create_override():
        return jsonify({"error": "Use the FastAPI /overrides endpoint"}), 501

    @advisor_bp.route("/overrides", methods=["GET"])
    def list_overrides():
        return jsonify({"error": "Use the FastAPI /overrides endpoint"}), 501
else:
    advisor_bp = None


class AdvisorOverrideAPI:
    """DB-backed override operations. Pass a SQLAlchemy `Session` on each call."""

    @staticmethod
    def create(
        db,
        client_id: int,
        advisor_id: int,
        original: Optional[Dict[str, Any]],
        replacement: Optional[Dict[str, Any]],
        reason: str,
    ):
        from backend.database.models import AdvisorOverride

        entry = AdvisorOverride(
            client_id=client_id,
            advisor_id=advisor_id,
            original=original,
            replacement=replacement,
            reason=reason,
            status="pending",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def get(db, override_id: int):
        from backend.database.models import AdvisorOverride

        return db.query(AdvisorOverride).filter(AdvisorOverride.id == override_id).first()

    @staticmethod
    def approve(db, override_id: int):
        from backend.database.models import AdvisorOverride

        entry = db.query(AdvisorOverride).filter(AdvisorOverride.id == override_id).first()
        if entry:
            entry.status = "approved"
            entry.approved_at = datetime.utcnow()
            db.commit()
            db.refresh(entry)
        return entry

    @staticmethod
    def reject(db, override_id: int, rejection_reason: str = ""):
        from backend.database.models import AdvisorOverride

        entry = db.query(AdvisorOverride).filter(AdvisorOverride.id == override_id).first()
        if entry:
            entry.status = "rejected"
            entry.rejected_at = datetime.utcnow()
            entry.rejection_reason = rejection_reason
            db.commit()
            db.refresh(entry)
        return entry

    @staticmethod
    def list_for_client(db, client_id: int, status: Optional[str] = None):
        from backend.database.models import AdvisorOverride

        q = db.query(AdvisorOverride).filter(AdvisorOverride.client_id == client_id)
        if status:
            q = q.filter(AdvisorOverride.status == status)
        return q.order_by(AdvisorOverride.created_at.desc()).all()


def apply_overrides(allocation: dict, user_data: dict) -> dict:
    """
    Apply rule-based advisor overrides to an allocation dict.

    Rules applied:
    - Clients over 55: minimum 40% debt allocation
    - Risk score below 4 (conservative): cap equity at 30%
    - Any key in allocation is preserved; only adjusted if rule triggers
    """
    if not allocation:
        return allocation

    result = dict(allocation)
    reasons = []

    try:
        age = user_data.get("age", 0)
        risk_score = user_data.get("risk_score", 5)

        # Rule 1: Age-based debt floor
        if age > 55 and result.get("debt", 100) < 40:
            excess = 40 - result.get("debt", 0)
            result["debt"] = 40
            result["equity"] = max(0, result.get("equity", 0) - excess)
            reasons.append(f"Age {age}: minimum 40% debt applied")

        # Rule 2: Conservative risk cap on equity
        if risk_score < 4 and result.get("equity", 0) > 30:
            excess = result["equity"] - 30
            result["equity"] = 30
            result["debt"] = result.get("debt", 0) + excess
            reasons.append(f"Risk score {risk_score}: equity capped at 30%")

        # Re-normalise to 100%
        total = sum(result.get(k, 0) for k in ["equity", "debt", "gold"])
        if total > 0 and abs(total - 100) > 0.5:
            for k in ["equity", "debt", "gold"]:
                if k in result:
                    result[k] = round(result[k] / total * 100, 2)

        result["override_applied"] = len(reasons) > 0
        result["override_reason"] = "; ".join(reasons) if reasons else ""

    except Exception as e:
        result["override_applied"] = False
        result["override_reason"] = f"Override skipped: {e}"

    return result
