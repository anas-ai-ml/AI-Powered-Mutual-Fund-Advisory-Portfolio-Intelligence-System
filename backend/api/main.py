from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.auth import get_current_advisor, router as auth_router
from backend.database.connection import get_db
from backend.database.init_db import init_db
from backend.database.models import (
    Advisor,
    AdvisorOverride,
    AuditLog,
    Client,
    GoalLine,
    IssuedReport,
    MeetingNote,
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
    occupation: Optional[str] = None
    income_bracket: Optional[str] = None
    investable_surplus: Optional[float] = None


class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    contact: Optional[str] = None
    pan_placeholder: Optional[str] = None
    city: Optional[str] = None
    source_channel: Optional[str] = None
    occupation: Optional[str] = None
    income_bracket: Optional[str] = None
    investable_surplus: Optional[float] = None
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


class MeetingNoteCreateRequest(BaseModel):
    raw_transcript: str
    ai_summary: Optional[str] = None
    structured_extractions: Optional[Dict[str, Any]] = None
    confidence_flags: Optional[Dict[str, Any]] = None


class ProposalCreateRequest(BaseModel):
    system_draft: Dict[str, Any]
    advisor_final: Optional[Dict[str, Any]] = None
    override_reason: Optional[str] = None
    category_rationale: Optional[str] = None
    sip_assumptions: Optional[Dict[str, Any]] = None
    benchmark_data: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = "draft"


class IssueReportRequest(BaseModel):
    report_type: str = "proposal_deck"


class AIExtractRequest(BaseModel):
    raw_transcript: str


class AdvisorProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    firm_name: Optional[str] = None
    phone: Optional[str] = None
    logo_path: Optional[str] = None


class OverrideCreateRequest(BaseModel):
    original: Optional[Dict[str, Any]] = None
    replacement: Optional[Dict[str, Any]] = None
    reason: str = ""


class OverrideRejectRequest(BaseModel):
    reason: str = ""


class ReviewReportRequest(BaseModel):
    notes: Optional[str] = None


AUDIT_ACTIONS = {
    "profile_edit",
    "proposal_generated",
    "report_issue",
    "report_issued",
    "analysis_viewed",
    "meeting_note_created",
    "proposal_approved",
    "report_issued",
}


def _serialize_meeting_note(note: MeetingNote) -> Dict[str, Any]:
    return {
        "id": note.id,
        "client_id": note.client_id,
        "advisor_id": note.advisor_id,
        "raw_transcript": note.raw_transcript,
        "ai_summary": note.ai_summary,
        "structured_extractions": note.structured_extractions or {},
        "confidence_flags": note.confidence_flags or {},
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "applied_to_profile": note.applied_to_profile,
    }


def _serialize_proposal_draft(draft: ProposalDraft) -> Dict[str, Any]:
    return {
        "id": draft.id,
        "client_id": draft.client_id,
        "system_draft": draft.system_draft,
        "advisor_final": draft.advisor_final,
        "override_reason": draft.override_reason,
        "status": draft.status,
        "version_number": draft.version_number,
        "category_rationale": draft.category_rationale,
        "sip_assumptions": draft.sip_assumptions or {},
        "benchmark_data": draft.benchmark_data or [],
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


def _serialize_issued_report(report: IssuedReport) -> Dict[str, Any]:
    return {
        "id": report.id,
        "proposal_id": report.proposal_id,
        "client_id": report.client_id,
        "issued_by": report.issued_by,
        "pdf_path": report.pdf_path,
        "version_number": report.version_number,
        "issue_date": report.issue_date.isoformat() if report.issue_date else None,
        "report_type": report.report_type,
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
        "occupation": client.occupation,
        "income_bracket": client.income_bracket,
        "investable_surplus": client.investable_surplus,
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
        occupation=payload.occupation,
        income_bracket=payload.income_bracket,
        investable_surplus=payload.investable_surplus,
        profile_data={
            "age": payload.age,
            "contact": payload.contact,
            "pan_placeholder": payload.pan_placeholder,
            "city": payload.city,
            "source_channel": payload.source_channel,
            "occupation": payload.occupation,
            "income_bracket": payload.income_bracket,
            "investable_surplus": payload.investable_surplus,
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
        "occupation": client.occupation,
        "income_bracket": client.income_bracket,
        "investable_surplus": client.investable_surplus,
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
        "occupation": client.occupation,
        "income_bracket": client.income_bracket,
        "investable_surplus": client.investable_surplus,
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


@app.post("/clients/{client_id}/meeting-notes")
def create_meeting_note(
    client_id: int,
    payload: MeetingNoteCreateRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    note = MeetingNote(
        client_id=client.id,
        advisor_id=current_advisor.id,
        raw_transcript=payload.raw_transcript,
        ai_summary=payload.ai_summary,
        structured_extractions=payload.structured_extractions,
        confidence_flags=payload.confidence_flags,
    )
    db.add(note)
    db.add(AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action="meeting_note_created",
        after_value={"ai_summary": payload.ai_summary},
        notes="Meeting note captured.",
    ))
    try:
        db.commit()
        db.refresh(note)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save meeting note: {exc}")
    return _serialize_meeting_note(note)


@app.get("/clients/{client_id}/meeting-notes")
def list_meeting_notes(
    client_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    notes = (
        db.query(MeetingNote)
        .filter(MeetingNote.client_id == client.id)
        .order_by(MeetingNote.created_at.desc())
        .all()
    )
    return [_serialize_meeting_note(n) for n in notes]


@app.post("/meeting-notes/{note_id}/apply-to-profile")
def apply_meeting_note_to_profile(
    note_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    note = db.query(MeetingNote).filter(MeetingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Meeting note not found")
    client = _get_accessible_client_or_404(db, current_advisor, note.client_id)
    extractions = note.structured_extractions or {}
    merged_profile = dict(client.profile_data or {})
    for key, value in extractions.items():
        if value is not None:
            merged_profile[key] = value
    client.profile_data = merged_profile
    if merged_profile.get("age") is not None:
        try:
            client.age = int(merged_profile["age"])
        except (TypeError, ValueError):
            pass
    note.applied_to_profile = True
    db.add(AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action="profile_edit",
        after_value={"source": "meeting_note", "note_id": note_id, "applied_fields": list(extractions.keys())},
        notes=f"Profile updated from meeting note #{note_id}.",
    ))
    try:
        db.commit()
        db.refresh(client)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply note: {exc}")
    latest_risk = _latest_risk_for_client(db, client.id)
    return _serialize_client(client, latest_risk=latest_risk)


@app.post("/clients/{client_id}/proposals")
def create_proposal(
    client_id: int,
    payload: ProposalCreateRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    version_number = (
        db.query(func.count(ProposalDraft.id))
        .filter(ProposalDraft.client_id == client.id)
        .scalar()
        or 0
    ) + 1
    draft = ProposalDraft(
        client_id=client.id,
        system_draft=payload.system_draft,
        advisor_final=payload.advisor_final,
        override_reason=payload.override_reason,
        status=payload.status or "draft",
        version_number=version_number,
        category_rationale=payload.category_rationale,
        sip_assumptions=payload.sip_assumptions,
        benchmark_data=payload.benchmark_data,
    )
    db.add(draft)
    db.add(AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action="proposal_generated",
        after_value={"version_number": version_number, "status": draft.status},
        notes=f"Proposal v{version_number} created.",
    ))
    try:
        db.commit()
        db.refresh(draft)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create proposal: {exc}")
    return _serialize_proposal_draft(draft)


@app.get("/clients/{client_id}/proposals")
def list_proposals(
    client_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    drafts = (
        db.query(ProposalDraft)
        .filter(ProposalDraft.client_id == client.id)
        .order_by(ProposalDraft.version_number.desc())
        .all()
    )
    return [_serialize_proposal_draft(d) for d in drafts]


@app.post("/clients/{client_id}/proposals/{proposal_id}/approve")
def approve_proposal(
    client_id: int,
    proposal_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    draft = db.query(ProposalDraft).filter(
        ProposalDraft.id == proposal_id,
        ProposalDraft.client_id == client.id,
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Proposal not found")
    draft.status = "approved"
    db.add(AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action="proposal_approved",
        after_value={"proposal_id": proposal_id, "version_number": draft.version_number},
        notes=f"Proposal v{draft.version_number} approved.",
    ))
    try:
        db.commit()
        db.refresh(draft)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to approve proposal: {exc}")
    return _serialize_proposal_draft(draft)


@app.post("/clients/{client_id}/proposals/{proposal_id}/issue")
def issue_proposal_report(
    client_id: int,
    proposal_id: int,
    payload: IssueReportRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    draft = db.query(ProposalDraft).filter(
        ProposalDraft.id == proposal_id,
        ProposalDraft.client_id == client.id,
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if draft.status not in ("approved", "reviewed", "overridden"):
        raise HTTPException(status_code=400, detail=f"Proposal must be approved before issuing. Current status: {draft.status}")
    reports_dir = Path("reports") / f"client_{client_id}"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"proposal_v{draft.version_number}_{timestamp}.pdf"
    pdf_path = str(reports_dir / pdf_filename)
    try:
        if payload.report_type == "vinsan_proposal":
            from backend.report.pdf_generator import generate_vinsan_proposal_pdf
            deck_data = {
                "cover": {
                    "client_name": client.name,
                    "risk_class": (draft.system_draft or {}).get("risk_profile", {}).get("category", "Moderate"),
                    "advisor_name": current_advisor.name,
                    "version_number": draft.version_number,
                },
                "category_rationale": {
                    "category_name": (draft.system_draft or {}).get("fund_category", "Mutual Fund"),
                    "rationale_text": draft.category_rationale or "",
                },
                "sip_matrix": draft.sip_assumptions or {},
                "benchmark_data": draft.benchmark_data or [],
                "advisor_contact": {
                    "name": current_advisor.name,
                    "email": current_advisor.email,
                    "firm_name": current_advisor.firm_name or "",
                    "phone": current_advisor.phone or "",
                },
                "version_number": draft.version_number,
                "issue_date": datetime.utcnow().strftime("%d %b %Y"),
            }
            generate_vinsan_proposal_pdf(deck_data, pdf_path)
        else:
            from backend.report.pdf_generator import generate_proposal_deck_pdf
            generate_proposal_deck_pdf(draft.system_draft or {}, pdf_path)
    except Exception as exc:
        pdf_path = None
    issued = IssuedReport(
        proposal_id=draft.id,
        client_id=client.id,
        issued_by=current_advisor.id,
        pdf_path=pdf_path,
        version_number=draft.version_number,
        report_type=payload.report_type,
    )
    db.add(issued)
    draft.status = "issued"
    db.add(AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action="report_issued",
        after_value={"proposal_id": proposal_id, "version_number": draft.version_number, "pdf_path": pdf_path},
        notes=f"Report v{draft.version_number} issued.",
    ))
    try:
        db.commit()
        db.refresh(issued)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to issue report: {exc}")
    return _serialize_issued_report(issued)


@app.get("/clients/{client_id}/issued-reports")
def list_issued_reports(
    client_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    reports = (
        db.query(IssuedReport)
        .filter(IssuedReport.client_id == client.id)
        .order_by(IssuedReport.issue_date.desc())
        .all()
    )
    return [_serialize_issued_report(r) for r in reports]


@app.post("/ai/extract-meeting-notes")
def extract_meeting_notes(
    payload: AIExtractRequest,
    current_advisor: Advisor = Depends(get_current_advisor),
):
    from backend.services.ai_note_extractor import extract_from_transcript
    result = extract_from_transcript(payload.raw_transcript)
    return result


@app.get("/audit-trail")
def get_global_audit_trail(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    query = db.query(AuditLog)
    if not _is_admin(current_advisor):
        client_ids = [
            c.id for c in db.query(Client.id).filter(Client.advisor_id == current_advisor.id).all()
        ]
        query = query.filter(AuditLog.client_id.in_(client_ids))
    entries = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [_serialize_audit_log(e) for e in entries]


# ── Advisor Profile ───────────────────────────────────────────────────────────

def _serialize_advisor(advisor: Advisor) -> Dict[str, Any]:
    return {
        "id": advisor.id,
        "email": advisor.email,
        "name": advisor.name,
        "role": advisor.role,
        "firm_name": advisor.firm_name,
        "phone": advisor.phone,
        "logo_path": advisor.logo_path,
        "created_at": advisor.created_at.isoformat() if advisor.created_at else None,
    }


@app.get("/auth/me/profile")
def get_advisor_profile(
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    return _serialize_advisor(current_advisor)


@app.put("/auth/me/profile")
def update_advisor_profile(
    payload: AdvisorProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    if payload.name is not None:
        current_advisor.name = payload.name
    if payload.firm_name is not None:
        current_advisor.firm_name = payload.firm_name
    if payload.phone is not None:
        current_advisor.phone = payload.phone
    if payload.logo_path is not None:
        current_advisor.logo_path = payload.logo_path
    try:
        db.commit()
        db.refresh(current_advisor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {exc}")
    return _serialize_advisor(current_advisor)


# ── Advisor Overrides (DB-persisted) ─────────────────────────────────────────

def _serialize_override(o: AdvisorOverride) -> Dict[str, Any]:
    return {
        "id": o.id,
        "client_id": o.client_id,
        "advisor_id": o.advisor_id,
        "original": o.original,
        "replacement": o.replacement,
        "reason": o.reason,
        "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "approved_at": o.approved_at.isoformat() if o.approved_at else None,
        "rejected_at": o.rejected_at.isoformat() if o.rejected_at else None,
        "rejection_reason": o.rejection_reason,
    }


@app.post("/clients/{client_id}/overrides")
def create_override(
    client_id: int,
    payload: OverrideCreateRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    from backend.api.advisor_overrides import AdvisorOverrideAPI
    entry = AdvisorOverrideAPI.create(
        db,
        client_id=client.id,
        advisor_id=current_advisor.id,
        original=payload.original,
        replacement=payload.replacement,
        reason=payload.reason,
    )
    db.add(AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action="override_created",
        before_value=payload.original,
        after_value=payload.replacement,
        notes=payload.reason or "Advisor override submitted.",
    ))
    db.commit()
    return _serialize_override(entry)


@app.get("/clients/{client_id}/overrides")
def list_overrides(
    client_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    client = _get_accessible_client_or_404(db, current_advisor, client_id)
    from backend.api.advisor_overrides import AdvisorOverrideAPI
    entries = AdvisorOverrideAPI.list_for_client(db, client.id, status=status)
    return [_serialize_override(e) for e in entries]


@app.post("/clients/{client_id}/overrides/{override_id}/approve")
def approve_override(
    client_id: int,
    override_id: int,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    _get_accessible_client_or_404(db, current_advisor, client_id)
    from backend.api.advisor_overrides import AdvisorOverrideAPI
    entry = AdvisorOverrideAPI.approve(db, override_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Override not found")
    return _serialize_override(entry)


@app.post("/clients/{client_id}/overrides/{override_id}/reject")
def reject_override(
    client_id: int,
    override_id: int,
    payload: OverrideRejectRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    _get_accessible_client_or_404(db, current_advisor, client_id)
    from backend.api.advisor_overrides import AdvisorOverrideAPI
    entry = AdvisorOverrideAPI.reject(db, override_id, payload.reason)
    if not entry:
        raise HTTPException(status_code=404, detail="Override not found")
    return _serialize_override(entry)


# ── Proposal Counts (global summary) ─────────────────────────────────────────

@app.get("/clients/proposal-counts")
def get_proposal_counts(
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    """Returns {client_id: proposal_count} for all accessible clients."""
    client_ids_query = db.query(Client.id)
    if not _is_admin(current_advisor):
        client_ids_query = client_ids_query.filter(Client.advisor_id == current_advisor.id)
    client_ids = [row[0] for row in client_ids_query.all()]

    rows = (
        db.query(ProposalDraft.client_id, func.count(ProposalDraft.id).label("count"))
        .filter(ProposalDraft.client_id.in_(client_ids))
        .group_by(ProposalDraft.client_id)
        .all()
    )
    return {str(row.client_id): row.count for row in rows}


# ── Review Report ─────────────────────────────────────────────────────────────

@app.post("/clients/{client_id}/review-report")
def generate_review_report(
    client_id: int,
    payload: ReviewReportRequest,
    db: Session = Depends(get_db),
    current_advisor: Advisor = Depends(get_current_advisor),
):
    """
    Generate a periodic review report PDF comparing current portfolio snapshot
    against the last issued proposal, enriched with audit history.
    """
    client = _get_accessible_client_or_404(db, current_advisor, client_id)

    latest_snapshot = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.client_id == client.id)
        .order_by(PortfolioSnapshot.created_at.desc())
        .first()
    )
    last_proposal = (
        db.query(ProposalDraft)
        .filter(ProposalDraft.client_id == client.id, ProposalDraft.status == "issued")
        .order_by(ProposalDraft.version_number.desc())
        .first()
    )
    recent_logs = (
        db.query(AuditLog)
        .filter(AuditLog.client_id == client.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(10)
        .all()
    )

    snapshot_data = {}
    if latest_snapshot:
        total = (latest_snapshot.equity or 0) + (latest_snapshot.fd_bonds or 0) + (latest_snapshot.gold or 0) + (latest_snapshot.cash or 0)
        snapshot_data = {
            "equity": latest_snapshot.equity or 0,
            "fd_bonds": latest_snapshot.fd_bonds or 0,
            "gold": latest_snapshot.gold or 0,
            "cash": latest_snapshot.cash or 0,
            "total": total,
            "notes": latest_snapshot.notes or "",
            "as_of": latest_snapshot.created_at.isoformat() if latest_snapshot.created_at else None,
        }

    from pathlib import Path as _Path
    reports_dir = _Path("reports") / f"client_{client_id}"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    pdf_path = str(reports_dir / f"review_{timestamp}.pdf")

    review_data = {
        "client_name": client.name,
        "advisor_name": current_advisor.name,
        "firm_name": current_advisor.firm_name or "",
        "advisor_email": current_advisor.email,
        "advisor_phone": current_advisor.phone or "",
        "review_date": datetime.utcnow().strftime("%d %b %Y"),
        "current_snapshot": snapshot_data,
        "last_proposal": {
            "version_number": last_proposal.version_number if last_proposal else None,
            "issued_date": last_proposal.created_at.isoformat() if last_proposal and last_proposal.created_at else None,
            "category_rationale": last_proposal.category_rationale if last_proposal else None,
            "system_draft": last_proposal.system_draft if last_proposal else {},
        },
        "activity_log": [_serialize_audit_log(e) for e in recent_logs],
        "advisor_notes": payload.notes or "",
    }

    try:
        from backend.report.pdf_generator import generate_review_report_pdf
        generate_review_report_pdf(review_data, pdf_path)
    except Exception as exc:
        pdf_path = None

    issued = IssuedReport(
        proposal_id=(last_proposal.id if last_proposal else
                     db.query(ProposalDraft).filter(ProposalDraft.client_id == client.id)
                     .order_by(ProposalDraft.version_number.desc()).first().id
                     if db.query(ProposalDraft).filter(ProposalDraft.client_id == client.id).first()
                     else None),
        client_id=client.id,
        issued_by=current_advisor.id,
        pdf_path=pdf_path,
        version_number=1,
        report_type="review_report",
    )
    if issued.proposal_id is not None:
        db.add(issued)
    db.add(AuditLog(
        client_id=client.id,
        advisor_id=current_advisor.id,
        action="review_report_generated",
        after_value={"pdf_path": pdf_path},
        notes="Periodic review report generated.",
    ))
    try:
        db.commit()
        if issued.proposal_id is not None:
            db.refresh(issued)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save review report record: {exc}")

    return {
        "pdf_path": pdf_path,
        "review_date": review_data["review_date"],
        "client_name": client.name,
        "report_type": "review_report",
    }


# ── Portal: client report viewer ──────────────────────────────────────────────

@app.get("/portal/client/{client_id}/reports")
def portal_get_client_reports(
    client_id: int,
    db: Session = Depends(get_db),
):
    """
    Public-ish endpoint for the client portal to fetch issued reports.
    No advisor auth required — client accesses by client_id.
    Returns only summary data (no private advisor info).
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    reports = (
        db.query(IssuedReport)
        .filter(IssuedReport.client_id == client_id)
        .order_by(IssuedReport.issue_date.desc())
        .all()
    )

    return {
        "client_name": client.name,
        "reports": [
            {
                "id": r.id,
                "report_type": r.report_type,
                "version_number": r.version_number,
                "issue_date": r.issue_date.isoformat() if r.issue_date else None,
                "pdf_available": bool(r.pdf_path),
                "pdf_path": r.pdf_path,
            }
            for r in reports
        ],
    }
