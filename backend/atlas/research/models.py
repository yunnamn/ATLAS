from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from atlas.db import Base, utcnow


def uid() -> str:
    return str(uuid4())


class ResearchRun(Base):
    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    objective: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    stop_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchPlan(Base):
    __tablename__ = "research_plans"
    __table_args__ = (UniqueConstraint("run_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    revision: Mapped[int] = mapped_column()
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchStep(Base):
    __tablename__ = "research_steps"
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column()
    node: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(String(1000))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceDocument(Base):
    __tablename__ = "research_documents"
    __table_args__ = (UniqueConstraint("url", "sha256"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    url: Mapped[str] = mapped_column(String(2000), index=True)
    title: Mapped[str] = mapped_column(String(200))
    media_type: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    raw_content: Mapped[bytes] = mapped_column(LargeBinary)
    locations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    links: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchCandidate(Base):
    __tablename__ = "research_candidates"
    __table_args__ = (UniqueConstraint("run_id", "url"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    url: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    discovered_from: Mapped[str | None] = mapped_column(
        ForeignKey("research_documents.id"), nullable=True
    )


class RunSource(Base):
    __tablename__ = "research_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_documents.id"), nullable=True
    )
    url: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(30))
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(String(300), default="")
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvidenceSnippet(Base):
    __tablename__ = "research_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("research_documents.id"))
    start: Mapped[int] = mapped_column()
    end: Mapped[int] = mapped_column()
    quote: Mapped[str] = mapped_column(Text)
    location: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    purpose: Mapped[str] = mapped_column(String(20))


class ExtractedClaim(Base):
    __tablename__ = "research_claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("research_documents.id"))
    field: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(Text)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON)
    proposed_quote: Mapped[str] = mapped_column(Text)
    proposed_scope_quote: Mapped[str] = mapped_column(Text)
    proposed_start: Mapped[int | None] = mapped_column(nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_evidence.id"), nullable=True
    )
    scope_evidence_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_evidence.id"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(30), default="unverified")
    normalized_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_note: Mapped[str] = mapped_column(String(300), default="Not yet checked")
    semantic_assessment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ResearchProposal(Base):
    __tablename__ = "research_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    target_opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True
    )
    expected_opportunity_revision: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    approval: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Contradiction(Base):
    __tablename__ = "research_contradictions"
    __table_args__ = (UniqueConstraint("run_id", "left_claim_id", "right_claim_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    left_claim_id: Mapped[str] = mapped_column(ForeignKey("research_claims.id"))
    right_claim_id: Mapped[str] = mapped_column(ForeignKey("research_claims.id"))
    field: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(String(500))


class ResearchReport(Base):
    __tablename__ = "research_reports"
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), primary_key=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
