from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from atlas.config import settings
from atlas.db import get_session, utc_iso
from atlas.research.errors import ResearchError
from atlas.research.manager import ResearchManager, capabilities
from atlas.research.models import (
    ResearchPlan,
    ResearchProposal,
    ResearchReport,
    ResearchRun,
    ResearchStep,
    RunSource,
    SourceDocument,
)
from atlas.research.proposals import (
    ProposalApproval,
    ProposalInput,
    approve,
    proposal_dict,
    propose,
)
from atlas.research.reporting import ledger
from atlas.research.schemas import RunInput
from atlas.research.verification import evidence_dict

router = APIRouter(prefix="/api/research", tags=["research-agent"])
DB = Annotated[Session, Depends(get_session)]


def get_manager(request: Request) -> ResearchManager:
    return cast(ResearchManager, request.app.state.research_manager)


Manager = Annotated[ResearchManager, Depends(get_manager)]


def get_run(session: Session, run_id: str) -> ResearchRun:
    row = session.get(ResearchRun, run_id)
    if not row:
        raise HTTPException(404, "Research run not found")
    return row


def run_dict(run: ResearchRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "objective": run.objective,
        "mode": run.mode,
        "status": run.status,
        "outcome": run.outcome,
        "stop_reason": run.stop_reason,
        "error": run.error,
        "cancel_requested": run.cancel_requested,
        "stats": run.stats,
        "state": run.state,
        "request": run.request,
        "created_at": utc_iso(run.created_at),
        "started_at": utc_iso(run.started_at) if run.started_at else None,
        "finished_at": utc_iso(run.finished_at) if run.finished_at else None,
    }


@router.get("/capabilities")
def get_capabilities() -> dict[str, Any]:
    return capabilities(settings)


@router.post("/runs", status_code=202)
def start_run(data: RunInput, manager: Manager) -> dict[str, str]:
    try:
        run_id = manager.submit(data)
    except ResearchError as exc:
        raise HTTPException(429 if exc.code == "worker_busy" else 409, exc.message) from exc
    return {"id": run_id, "status": "pending"}


@router.get("/runs")
def list_runs(session: DB, limit: int = Query(default=20, ge=1, le=50)) -> list[dict[str, Any]]:
    return [
        run_dict(run)
        for run in session.scalars(
            select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(limit)
        )
    ]


@router.get("/runs/{run_id}")
def inspect_run(run_id: str, session: DB) -> dict[str, Any]:
    run = get_run(session, run_id)
    plans = [
        {"revision": p.revision, "content": p.content, "created_at": utc_iso(p.created_at)}
        for p in session.scalars(
            select(ResearchPlan)
            .where(ResearchPlan.run_id == run_id)
            .order_by(ResearchPlan.revision)
        )
    ]
    steps = [
        {
            "id": s.id,
            "sequence": s.sequence,
            "node": s.node,
            "summary": s.summary,
            "data": s.data,
            "checkpoint": s.checkpoint,
            "created_at": utc_iso(s.created_at),
        }
        for s in session.scalars(
            select(ResearchStep)
            .where(ResearchStep.run_id == run_id)
            .order_by(ResearchStep.sequence)
        )
    ]
    return {**run_dict(run), "plans": plans, "steps": steps}


@router.get("/runs/{run_id}/evidence")
def get_evidence(run_id: str, session: DB) -> dict[str, Any]:
    data = ledger(session, get_run(session, run_id))
    return {
        "sources": [
            {
                "id": s.id,
                "document_id": s.document_id,
                "url": s.url,
                "status": s.status,
                "cache_hit": s.cache_hit,
                "message": s.message,
                "used_at": utc_iso(s.used_at),
            }
            for s in data["sources"]
        ],
        "documents": [
            {
                "id": d.id,
                "url": d.url,
                "title": d.title,
                "sha256": d.sha256,
                "media_type": d.media_type,
                "synthetic": d.synthetic,
                "fetched_at": utc_iso(d.fetched_at),
                "last_checked_at": utc_iso(d.last_checked_at),
            }
            for d in data["documents"].values()
        ],
        "snippets": [evidence_dict(e, data["documents"][e.document_id]) for e in data["evidence"]],
        "claims": [
            {
                "id": c.id,
                "document_id": c.document_id,
                "field": c.field,
                "value": c.value,
                "scope": c.scope,
                "state": c.state,
                "evidence_id": c.evidence_id,
                "scope_evidence_id": c.scope_evidence_id,
                "verification_note": c.verification_note,
                "semantic_assessment": c.semantic_assessment,
            }
            for c in data["claims"]
        ],
        "contradictions": [
            {
                "id": c.id,
                "field": c.field,
                "summary": c.summary,
                "claim_ids": [c.left_claim_id, c.right_claim_id],
            }
            for c in data["contradictions"]
        ],
        "unknowns": data["missing"],
        "question_assessments": data["question_assessments"],
        "context_differences": data["context_differences"],
    }


@router.get("/runs/{run_id}/documents/{document_id}")
def get_document(run_id: str, document_id: str, session: DB) -> dict[str, Any]:
    get_run(session, run_id)
    source = session.scalar(
        select(RunSource).where(RunSource.run_id == run_id, RunSource.document_id == document_id)
    )
    doc = session.get(SourceDocument, document_id) if source else None
    if not doc:
        raise HTTPException(404, "Source document is not attached to this run")
    return {
        "id": doc.id,
        "url": doc.url,
        "title": doc.title,
        "text": doc.text,
        "sha256": doc.sha256,
        "locations": doc.locations,
        "synthetic": doc.synthetic,
        "fetched_at": utc_iso(doc.fetched_at),
        "last_checked_at": utc_iso(doc.last_checked_at),
    }


@router.get("/runs/{run_id}/report")
def get_report(run_id: str, session: DB) -> dict[str, Any]:
    get_run(session, run_id)
    report = session.get(ResearchReport, run_id)
    if not report:
        raise HTTPException(409, "Report is not ready; inspect run progress")
    return report.content


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str, manager: Manager, session: DB) -> dict[str, str]:
    get_run(session, run_id)
    manager.cancel(run_id)
    return {"id": run_id, "status": "cancellation_requested"}


@router.get("/runs/{run_id}/proposals")
def list_proposals(run_id: str, session: DB) -> list[dict[str, Any]]:
    get_run(session, run_id)
    return [
        proposal_dict(row)
        for row in session.scalars(
            select(ResearchProposal)
            .where(ResearchProposal.run_id == run_id)
            .order_by(ResearchProposal.created_at.desc())
            .limit(50)
        )
    ]


@router.post("/runs/{run_id}/proposals", status_code=201)
def create_proposal(run_id: str, data: ProposalInput, session: DB) -> dict[str, Any]:
    return proposal_dict(propose(session, get_run(session, run_id), data))


@router.post("/runs/{run_id}/proposals/{proposal_id}/approve")
def approve_proposal(
    run_id: str,
    proposal_id: str,
    data: ProposalApproval,
    session: DB,
) -> dict[str, Any]:
    get_run(session, run_id)
    proposal = session.get(ResearchProposal, proposal_id)
    if not proposal or proposal.run_id != run_id:
        raise HTTPException(404, "Proposal not found for this run")
    try:
        return proposal_dict(approve(session, proposal, data))
    except (IntegrityError, StaleDataError) as exc:
        session.rollback()
        raise HTTPException(
            409, "Record identity/revision changed; inspect before retrying"
        ) from exc
    except ValidationError as exc:
        session.rollback()
        raise HTTPException(422, "Proposed record exceeds directory schema constraints") from exc
