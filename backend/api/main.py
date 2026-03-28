from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.auth import get_current_advisor, router as auth_router
from backend.database.connection import get_db
from backend.database.init_db import init_db
from backend.database.models import (
    Advisor,
    AuditLog,
    Client,
    GoalLine,
    PortfolioSnapshot,
    ProposalDraft,
    RiskQuestionnaire,
)
from backend.engines.allocation_engine import get_asset_allocation
from backend.engines.goal_engine import calculate_child_education_goal, calculate_retirement_goal
from backend.engines.monte_carlo_engine import run_monte_carlo_simulation
from backend.engines.risk_engine import calculate_risk_score
from backend.models.client_model import ClientModel


init_db()

app = FastAPI(title="AI-Powered Financial Intelligence Engine API")
app.include_router(auth_router)


class RetirementRequest(BaseModel):
    current_age: int
    current_monthly_expense: float
    expected_return_rate: float


class EducationRequest(BaseModel):
    present_cost: float
    years_to_goal: int
    expected_return_rate: float


class ClientCreateRequest(BaseModel):
    name: str
    age: int
    contact: Optional[str] = None
    pan_placeholder: Optional[str] = None
    city: Optional[str] = None
    source_channel: Optional[str] = None


class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    contact: Optional[str] = None
    pan_placeholder: Optional[str] = None
    city: Optional[str] = None
    source_channel: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None


class SaveAnalysisRequest(BaseModel):
    risk: Dict[str, Any]
    goals: List[Dict[str, Any]]
    portfolio: Dict[str, Any] = Field(default_factory=dict)
    proposal_draft: Dict[str, Any]
    advisor_final: Optional[Dict[str, Any]] = None
    override_reason: Optional[str] = None
    proposal_status: Optional[str] = None
    client_profile: Optional[Dict[str, Any]] = None


class AuditLogRequest(BaseModel):
    action: str
    before_value: Optional[Dict[str, Any]] = None
    after_value: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


AUDIT_ACTIONS = {
    "profile_edit",
    "proposal_generated",
    "report_issue",
    "report_issued",
    "analysis_viewed",
}


def _serialize_client(client: Client, latest_risk: Optional[RiskQuestionnaire] = None) -> Dict[str, Any]:
    return {
        "id": client.id,
        "advisor_id": client.advisor_id,
        "advisor_name": client.advisor.name if getattr(client, "advisor", None) else None,
        "name": client.name,
        "age": client.age,
        "contact": client.contact,
        "pan_placeholder": client.pan_placeholder,
        "city": client.city,
        "source_channel": client.source_channel,
        "profile_data": client.profile_data or {},
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "risk_class": latest_risk.risk_class if latest_risk else None,
        "risk_score": latest_risk.score if latest_risk else None,
    }


def _serialize_audit_log(entry: AuditLog) -> Dict[str, Any]:
    return {
        "log_id": entry.id,
        "client_id": entry.client_id,
        "advisor_id": entry.advisor_id,
        "action": entry.action,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "before_value": entry.before_value,
        "after_value": entry.after_value,
        "notes": entry.notes,
    }


def _is_admin(user: Advisor) -> bool:
    return str(user.role).lower() == "admin"


def _get_accessible_client_or_404(
    db: Session,
    current_advisor: Advisor,
    client_id: int,
) -> Client:
    query = db.query(Client).filter(Client.id == client_id)
    if not _is_admin(current_advisor):
        query = query.filter(Client.advisor_id == current_advisor.id)
    client = query.first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def _latest_risk_for_client(db: Session, client_id: int) -> Optional[RiskQuestionnaire]:
    return (
        db.query(RiskQuestionnaire)
        .filter(RiskQuestionnaire.client_id == client_id)
        .order_by(RiskQuestionnaire.created_at.desc())
        .first()
    )


def _extract_allocation_weights(payload: Any) -> Dict[str, float]:
    if not isinstance(payload, dict):
        return {}
    allocation = payload.get("allocation") if isinstance(payload.get("allocation"), dict) else payload
    weights: Dict[str, float] = {}
    for key, value in allocation.items():
        try:
            weights[str(key)] = round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return weights


def _allocations_differ(system_allocation: Dict[str, float], advisor_allocation: Dict[str, float]) -> bool:
    keys = set(system_allocation) | set(advisor_allocation)
    return any(
        abs(float(system_allocation.get(key, 0.0)) - float(advisor_allocation.get(key, 0.0))) > 0.05
        for key in keys
    )


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Financial Intelligence Engine is running"}


@app.post("/api/risk-profile")
def get_risk_profile(client: ClientModel):
    try:
        return calculate_risk_score(
            age=client.age,
            dependents=client.dependents,
            behavior=client.behavior_traits,
            monthly_income=client.monthly_income,
            monthly_savings=client.monthly_savings_capacity,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/goal/retirement")
def evaluate_retirement(req: RetirementRequest):
    return calculate_retirement_goal(
        req.current_age, req.current_monthly_expense, req.expected_return_rate
    )


@app.post("/api/goal/education")
def evaluate_education(req: EducationRequest):
    return calculate_child_education_goal(
        req.present_cost, req.years_to_goal, req.expected_return_rate
    )


@app.get("/api/allocation")
def get_allocation(risk_score: float):
    return get_asset_allocation(risk_score)


@app.post("/clients/")
def create_client(
    payload: ClientCreateRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = Client(
        advisor_id=current_advisor.id,
        name=payload.name.strip(),
        age=payload.age,
        contact=payload.contact,
        pan_placeholder=payload.pan_placeholder,
        city=payload.city,
        source_channel=payload.source_channel,
        profile_data={
            "age": payload.age,
            "contact": payload.contact,
            "pan_placeholder": payload.pan_placeholder,
            "city": payload.city,
            "source_channel": payload.source_channel,
        },
    )
    try:
        db.add(client)
        db.commit()
        db.refresh(client)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create client: {exc}")
    return _serialize_client(client)


@app.get("/clients/")
def list_clients(
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    query = db.query(Client)
    if not _is_admin(current_advisor):
        query = query.filter(Client.advisor_id == current_advisor.id)
    clients = query.order_by(Client.created_at.desc(), Client.name.asc()).all()
    results = []
    for client in clients:
        results.append(_serialize_client(client, latest_risk=_latest_risk_for_client(db, client.id)))
    return results


@app.get("/clients/{client_id}")
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    latest_risk = _latest_risk_for_client(db, client.id)
    latest_portfolio = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.client_id == client.id)
        .order_by(PortfolioSnapshot.created_at.desc())
        .first()
    )
    latest_draft = (
        db.query(ProposalDraft)
        .filter(ProposalDraft.client_id == client.id)
        .order_by(ProposalDraft.created_at.desc())
        .first()
    )
    goal_lines = (
        db.query(GoalLine)
        .filter(GoalLine.client_id == client.id)
        .order_by(GoalLine.priority.asc(), GoalLine.id.asc())
        .all()
    )

    return {
        **_serialize_client(client, latest_risk=latest_risk),
        "analysis": {
            "risk_questionnaire": {
                "id": latest_risk.id,
                "answers": latest_risk.answers,
                "score": latest_risk.score,
                "risk_class": latest_risk.risk_class,
                "override_reason": latest_risk.override_reason,
                "created_at": latest_risk.created_at.isoformat(),
            }
            if latest_risk
            else None,
            "goal_lines": [
                {
                    "id": goal.id,
                    "goal_type": goal.goal_type,
                    "target_amount": goal.target_amount,
                    "horizon_years": goal.horizon_years,
                    "priority": goal.priority,
                }
                for goal in goal_lines
            ],
            "portfolio_snapshot": {
                "id": latest_portfolio.id,
                "fd_bonds": latest_portfolio.fd_bonds,
                "gold": latest_portfolio.gold,
                "cash": latest_portfolio.cash,
                "equity": latest_portfolio.equity,
                "notes": latest_portfolio.notes,
                "created_at": latest_portfolio.created_at.isoformat(),
            }
            if latest_portfolio
            else None,
            "proposal_draft": {
                "id": latest_draft.id,
                "system_draft": latest_draft.system_draft,
                "advisor_final": latest_draft.advisor_final,
                "override_reason": latest_draft.override_reason,
                "status": latest_draft.status,
                "created_at": latest_draft.created_at.isoformat(),
            }
            if latest_draft
            else None,
        },
    }


@app.put("/clients/{client_id}")
def update_client(
    client_id: int,
    payload: ClientUpdateRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    before_value = {
        "name": client.name,
        "age": client.age,
        "contact": client.contact,
        "pan_placeholder": client.pan_placeholder,
        "city": client.city,
        "source_channel": client.source_channel,
        "profile_data": dict(client.profile_data or {}),
    }
    update_data = payload.model_dump(exclude_unset=True)
    profile_data = update_data.pop("profile_data", None)

    for field, value in update_data.items():
        setattr(client, field, value)

    if profile_data is not None:
        merged_profile = dict(client.profile_data or {})
        merged_profile.update(profile_data)
        client.profile_data = merged_profile
        if "age" in merged_profile:
            client.age = int(merged_profile["age"])

    after_value = {
        "name": client.name,
        "age": client.age,
        "contact": client.contact,
        "pan_placeholder": client.pan_placeholder,
        "city": client.city,
        "source_channel": client.source_channel,
        "profile_data": dict(client.profile_data or {}),
    }
    db.add(
        AuditLog(
            client_id=client.id,
            advisor_id=current_advisor.id,
            action="profile_edit",
            before_value=before_value,
            after_value=after_value,
            notes="Client profile updated by advisor.",
        )
    )

    try:
        db.commit()
        db.refresh(client)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update client: {exc}")

    latest_risk = _latest_risk_for_client(db, client.id)
    return _serialize_client(client, latest_risk=latest_risk)


@app.post("/clients/{client_id}/save-analysis")
def save_analysis(
    client_id: int,
    payload: SaveAnalysisRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)

    latest_draft = (
        db.query(ProposalDraft)
        .filter(ProposalDraft.client_id == client.id)
        .order_by(ProposalDraft.created_at.desc())
        .first()
    )
    before_value = (
        {
            "system_draft": latest_draft.system_draft,
            "advisor_final": latest_draft.advisor_final,
            "override_reason": latest_draft.override_reason,
            "status": latest_draft.status,
        }
        if latest_draft
        else None
    )

    advisor_final_payload = payload.advisor_final or {}
    system_risk_class = str(
        payload.proposal_draft.get("risk_profile", {}).get("category")
        or payload.risk.get("category")
        or "Unknown"
    )
    advisor_risk_class = str(
        advisor_final_payload.get("risk_class")
        or advisor_final_payload.get("risk_profile", {}).get("category")
        or system_risk_class
    )
    system_allocation = _extract_allocation_weights(payload.proposal_draft.get("target_allocation", {}))
    advisor_allocation = _extract_allocation_weights(
        advisor_final_payload.get("allocation")
        if isinstance(advisor_final_payload.get("allocation"), dict)
        else advisor_final_payload.get("target_allocation", {})
    )
    risk_override_changed = advisor_risk_class != system_risk_class
    allocation_override_changed = bool(advisor_allocation) and _allocations_differ(
        system_allocation,
        advisor_allocation,
    )
    override_reason = (payload.override_reason or "").strip() or None

    if (risk_override_changed or allocation_override_changed) and not override_reason:
        raise HTTPException(
            status_code=400,
            detail="Advisor override reason is required when changing risk class or allocation.",
        )

    if advisor_allocation:
        total_allocation = round(sum(advisor_allocation.values()), 2)
        if abs(total_allocation - 100.0) > 0.1:
            raise HTTPException(
                status_code=400,
                detail=f"Advisor final allocation must total 100%. Current total: {total_allocation:.2f}%",
            )

    try:
        if payload.client_profile:
            merged_profile = dict(client.profile_data or {})
            merged_profile.update(payload.client_profile)
            client.profile_data = merged_profile
            if merged_profile.get("age") is not None:
                client.age = int(merged_profile["age"])

        risk_entry = RiskQuestionnaire(
            client_id=client.id,
            answers=(payload.client_profile or client.profile_data or {}),
            score=float(payload.risk.get("score", 0.0)),
            risk_class=advisor_risk_class,
            override_reason=override_reason or payload.risk.get("override_reason"),
        )
        db.add(risk_entry)

        db.query(GoalLine).filter(GoalLine.client_id == client.id).delete()
        for idx, goal in enumerate(payload.goals, start=1):
            db.add(
                GoalLine(
                    client_id=client.id,
                    goal_type=str(goal.get("goal_type") or goal.get("goal_name") or goal.get("name") or f"goal_{idx}"),
                    target_amount=float(goal.get("future_corpus", goal.get("target_amount", 0.0))),
                    horizon_years=int(goal.get("years_to_goal", goal.get("horizon_years", 0))),
                    priority=int(goal.get("priority", idx)),
                )
            )

        profile_data = payload.client_profile or client.profile_data or {}
        portfolio_notes = None
        if payload.portfolio:
            portfolio_notes = ", ".join(payload.portfolio.get("insights", [])[:3]) or None

        db.add(
            PortfolioSnapshot(
                client_id=client.id,
                fd_bonds=float(profile_data.get("existing_fd", 0.0)),
                gold=float(profile_data.get("existing_gold", 0.0)),
                cash=float(profile_data.get("existing_savings", 0.0)),
                equity=float(profile_data.get("existing_mutual_funds", 0.0)),
                notes=portfolio_notes,
            )
        )

        draft = ProposalDraft(
            client_id=client.id,
            system_draft=payload.proposal_draft,
            advisor_final=advisor_final_payload or None,
            override_reason=override_reason,
            status=payload.proposal_status
            or ("overridden" if override_reason else "reviewed"),
        )
        db.add(draft)

        audit_after_value = {
            "system_draft": payload.proposal_draft,
            "advisor_final": advisor_final_payload or None,
            "override_reason": override_reason,
            "status": draft.status,
        }
        db.add(
            AuditLog(
                client_id=client.id,
                advisor_id=current_advisor.id,
                action="proposal_generated",
                before_value=before_value,
                after_value=audit_after_value,
                notes=f"Proposal draft saved with status `{draft.status}`.",
            )
        )

        db.commit()
        db.refresh(draft)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save analysis: {exc}")

    return {
        "status": "ok",
        "message": "Analysis saved",
        "client_id": client.id,
        "proposal_draft_id": draft.id,
        "saved_at": datetime.utcnow().isoformat(),
    }


@app.get("/clients/{client_id}/audit-trail")
def get_client_audit_trail(
    client_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.client_id == client.id)
        .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
        .all()
    )
    return [_serialize_audit_log(entry) for entry in entries]


@app.post("/clients/{client_id}/audit-log")
def create_audit_log(
    client_id: int,
    payload: AuditLogRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    action = str(payload.action).strip().lower()
    if action not in AUDIT_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audit action: {payload.action}",
        )
    entry = AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action=action,
        before_value=payload.before_value,
        after_value=payload.after_value,
        notes=payload.notes,
    )
    try:
        db.add(entry)
        db.commit()
        db.refresh(entry)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create audit log: {exc}")
    return _serialize_audit_log(entry)
