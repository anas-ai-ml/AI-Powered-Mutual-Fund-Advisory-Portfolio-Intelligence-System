from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Advisor(Base):
    __tablename__ = "advisors"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="advisor")
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
    audit_logs = relationship("AuditLog", back_populates="client", cascade="all, delete-orphan")


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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    client = relationship("Client", back_populates="proposal_drafts")


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
