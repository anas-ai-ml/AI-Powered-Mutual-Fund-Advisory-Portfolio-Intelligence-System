from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Advisor(Base):
    __tablename__ = "advisors"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="advisor")
    firm_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    logo_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    clients = relationship("Client", back_populates="advisor", cascade="all, delete-orphan")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    advisor_id = Column(Integer, ForeignKey("advisors.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    contact = Column(String(255), nullable=True)
    pan_placeholder = Column(String(50), nullable=True)
    city = Column(String(255), nullable=True)
    source_channel = Column(String(255), nullable=True)
    occupation = Column(String(255), nullable=True)
    income_bracket = Column(String(100), nullable=True)
    investable_surplus = Column(Float, nullable=True)
    profile_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    advisor = relationship("Advisor", back_populates="clients")
    risk_questionnaires = relationship(
        "RiskQuestionnaire", back_populates="client", cascade="all, delete-orphan"
    )
    goal_lines = relationship("GoalLine", back_populates="client", cascade="all, delete-orphan")
    portfolio_snapshots = relationship(
        "PortfolioSnapshot", back_populates="client", cascade="all, delete-orphan"
    )
    proposal_drafts = relationship(
        "ProposalDraft", back_populates="client", cascade="all, delete-orphan"
    )
    meeting_notes = relationship("MeetingNote", back_populates="client", cascade="all, delete-orphan")
    issued_reports = relationship("IssuedReport", back_populates="client", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="client", cascade="all, delete-orphan")
    advisor_overrides = relationship("AdvisorOverride", back_populates="client", cascade="all, delete-orphan")


class RiskQuestionnaire(Base):
    __tablename__ = "risk_questionnaires"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    answers = Column(JSON, nullable=False)
    score = Column(Float, nullable=False)
    risk_class = Column(String(100), nullable=False)
    override_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    client = relationship("Client", back_populates="risk_questionnaires")


class GoalLine(Base):
    __tablename__ = "goal_lines"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    goal_type = Column(String(100), nullable=False)
    target_amount = Column(Float, nullable=False)
    horizon_years = Column(Integer, nullable=False)
    priority = Column(Integer, nullable=False)

    client = relationship("Client", back_populates="goal_lines")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    fd_bonds = Column(Float, nullable=False, default=0.0)
    gold = Column(Float, nullable=False, default=0.0)
    cash = Column(Float, nullable=False, default=0.0)
    equity = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    client = relationship("Client", back_populates="portfolio_snapshots")


class ProposalDraft(Base):
    __tablename__ = "proposal_drafts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    system_draft = Column(JSON, nullable=False)
    advisor_final = Column(JSON, nullable=True)
    override_reason = Column(String(1000), nullable=True)
    status = Column(String(50), nullable=False, default="draft")
    version_number = Column(Integer, nullable=False, default=1)
    category_rationale = Column(Text, nullable=True)
    sip_assumptions = Column(JSON, nullable=True)
    benchmark_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    client = relationship("Client", back_populates="proposal_drafts")
    issued_reports = relationship("IssuedReport", back_populates="proposal", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    advisor_id = Column(Integer, ForeignKey("advisors.id"), nullable=False, index=True)
    action = Column(String(255), nullable=False)
    before_value = Column(JSON, nullable=True)
    after_value = Column(JSON, nullable=True)
    notes = Column(String(1000), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    client = relationship("Client", back_populates="audit_logs")
    advisor = relationship("Advisor")


class MeetingNote(Base):
    __tablename__ = "meeting_notes"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    advisor_id = Column(Integer, ForeignKey("advisors.id"), nullable=False, index=True)
    raw_transcript = Column(Text, nullable=False)
    ai_summary = Column(Text, nullable=True)
    structured_extractions = Column(JSON, nullable=True)
    confidence_flags = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    applied_to_profile = Column(Boolean, nullable=False, default=False)

    client = relationship("Client", back_populates="meeting_notes")
    advisor = relationship("Advisor")


class AdvisorOverride(Base):
    __tablename__ = "advisor_overrides"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    advisor_id = Column(Integer, ForeignKey("advisors.id"), nullable=False, index=True)
    original = Column(JSON, nullable=True)
    replacement = Column(JSON, nullable=True)
    reason = Column(String(1000), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(500), nullable=True)

    client = relationship("Client", back_populates="advisor_overrides")
    advisor = relationship("Advisor")


class IssuedReport(Base):
    __tablename__ = "issued_reports"

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(Integer, ForeignKey("proposal_drafts.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    issued_by = Column(Integer, ForeignKey("advisors.id"), nullable=False, index=True)
    pdf_path = Column(String(500), nullable=True)
    version_number = Column(Integer, nullable=False, default=1)
    issue_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    report_type = Column(String(50), nullable=False, default="proposal_deck")

    client = relationship("Client", back_populates="issued_reports")
    proposal = relationship("ProposalDraft", back_populates="issued_reports")
    advisor = relationship("Advisor")
