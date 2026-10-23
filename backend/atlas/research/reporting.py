from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db import utc_iso, utcnow
from atlas.research.intelligence import (
    contextual_differences,
    question_sufficiency,
    temporal_warnings,
)
from atlas.research.models import (
    Contradiction,
    EvidenceSnippet,
    ExtractedClaim,
    ResearchPlan,
    ResearchRun,
    RunSource,
    SourceDocument,
)
from atlas.research.verification import SUPPORTED, evidence_dict


def required_fields(plans: list[ResearchPlan]) -> list[str]:
    return sorted(
        {
            field
            for plan in plans
            for question in plan.content["questions"]
            for field in question["fields"]
        }
    )


def ledger(session: Session, run: ResearchRun) -> dict[str, Any]:
    plans = list(
        session.scalars(
            select(ResearchPlan)
            .where(ResearchPlan.run_id == run.id)
            .order_by(ResearchPlan.revision)
        )
    )
    claims = list(session.scalars(select(ExtractedClaim).where(ExtractedClaim.run_id == run.id)))
    evidence = list(
        session.scalars(select(EvidenceSnippet).where(EvidenceSnippet.run_id == run.id))
    )
    sources = list(session.scalars(select(RunSource).where(RunSource.run_id == run.id)))
    document_ids = {s.document_id for s in sources if s.document_id}
    documents = (
        {
            d.id: d
            for d in session.scalars(
                select(SourceDocument).where(SourceDocument.id.in_(document_ids))
            )
        }
        if document_ids
        else {}
    )
    supported = [c for c in claims if c.state in SUPPORTED]
    scopes = {str(c.scope): c.scope for c in supported}
    missing = []
    for scope in scopes.values() or [None]:
        present = {c.field for c in supported if scope is None or c.scope == scope}
        for field in required_fields(plans):
            if field not in present:
                missing.append(
                    {
                        "scope": scope,
                        "field": field,
                        "reason": "No source-supported evidence recorded",
                    }
                )
    contradictions = list(
        session.scalars(select(Contradiction).where(Contradiction.run_id == run.id))
    )
    return {
        "plans": plans,
        "claims": claims,
        "supported": supported,
        "evidence": evidence,
        "sources": sources,
        "documents": documents,
        "scopes": list(scopes.values()),
        "missing": missing,
        "contradictions": contradictions,
        "question_assessments": question_sufficiency(plans, supported, list(scopes.values())),
        "context_differences": contextual_differences(claims, documents),
        "temporal_warnings": temporal_warnings(supported, run.created_at.date()),
    }


def build_report(session: Session, run: ResearchRun, reason: str) -> dict[str, Any]:
    data = ledger(session, run)
    findings = [
        {
            "claim_id": c.id,
            "scope": c.scope,
            "field": c.field,
            "value": c.value,
            "state": c.state,
            "evidence_id": c.evidence_id,
            "scope_evidence_id": c.scope_evidence_id,
            "semantic_assessment": c.semantic_assessment,
        }
        for c in data["supported"]
    ]
    conflicts = [
        {
            "id": c.id,
            "field": c.field,
            "summary": c.summary,
            "claim_ids": [c.left_claim_id, c.right_claim_id],
        }
        for c in data["contradictions"]
    ]
    adequate = (
        bool(findings)
        and not data["missing"]
        and not conflicts
        and all(q["status"] == "supported" for q in data["question_assessments"])
    )
    partial = not adequate or reason != "model_stop"
    if reason in ("cancelled", "interrupted", "provider_unavailable", "model_schema_error"):
        partial = True
    prefix = "SYNTHETIC OFFLINE DEMONSTRATION. " if run.mode == "demo" else ""
    summary = (
        f"{prefix}Examined {len(data['documents'])} saved source documents. "
        f"Recorded {len(findings)} source-linked claims for {len(data['scopes'])} "
        f"program/intake scopes; {len(conflicts)} potential conflicts and "
        f"{len(data['missing'])} unanswered required fields remain. "
        + (
            "This is a partial report."
            if partial
            else "Required fields have evidence; human review of completion criteria is needed."
        )
    )
    return {
        "run_id": run.id,
        "mode": run.mode,
        "synthetic": run.mode == "demo",
        "outcome": "partial" if partial else "complete",
        "executive_summary": summary,
        "investigated_opportunities": data["scopes"],
        "findings": findings,
        "conflicts": conflicts,
        "unanswered_questions": data["missing"],
        "question_assessments": data["question_assessments"],
        "context_differences": data["context_differences"],
        "temporal_warnings": data["temporal_warnings"],
        "evidence_assessments": [
            {"claim_id": c.id, "field": c.field, **c.semantic_assessment}
            for c in data["claims"]
            if c.semantic_assessment
        ],
        "unverified_candidate_count": sum(c.state == "unverified" for c in data["claims"]),
        "recommended_next_investigations": [
            f"Check official evidence for {item['field'].replace('_', ' ')}"
            for item in data["missing"]
        ]
        + (
            ["Resolve document scope, conditions, and dates behind conflicting claims"]
            if conflicts
            else []
        ),
        "evidence": [
            evidence_dict(e, data["documents"][e.document_id])
            for e in data["evidence"]
            if e.document_id in data["documents"]
        ],
        "sources": [
            {
                "id": s.id,
                "document_id": s.document_id,
                "url": s.url,
                "status": s.status,
                "cache_hit": s.cache_hit,
                "message": s.message,
                "fetched_at": utc_iso(data["documents"][s.document_id].fetched_at)
                if s.document_id in data["documents"]
                else None,
                "last_checked_at": utc_iso(data["documents"][s.document_id].last_checked_at)
                if s.document_id in data["documents"]
                else None,
                "sha256": data["documents"][s.document_id].sha256
                if s.document_id in data["documents"]
                else None,
            }
            for s in data["sources"]
        ],
        "run_metadata": {
            "stop_reason": reason,
            "stats": run.stats,
            "llm_driven": run.mode == "live" and run.stats.get("model_http_requests", 0) > 0,
            "generated_at": utc_iso(utcnow()),
            "plan_revisions": len(data["plans"]),
        },
        "limitations": [
            "Source support means exact quotation and scope checks, not "
            "independent verification of truth or a complete eligibility assessment.",
            "Semantic labels use conservative English rules over bounded source context; "
            "they are not independently annotated entailment judgments. Question sufficiency "
            "checks field coverage, not arbitrary natural-language completion criteria.",
            "Only explicit domain scope is allowed. Official ownership is "
            "asserted by the user, not authenticated by ATLAS.",
            "Corroboration requires caller-declared independent source groups and "
            "distinct document hashes; these independence assertions need review.",
            "Conflicts use conservative normalized values; complex prose, "
            "conditional rules and dates can require manual comparison.",
            "Original PDFs and normalized text are retained as versioned evidence; "
            "cached sources show their last actual verification date.",
            "No admissions probability, applications, account modifications, "
            "or external side effects are produced.",
        ],
    }
