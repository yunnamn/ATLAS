"""Human-selected, transactional research promotion. Retrieved text never authorizes a write."""

from datetime import date
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db import Change, Opportunity, utc_iso, utcnow
from atlas.research.models import (
    EvidenceSnippet,
    ExtractedClaim,
    ResearchProposal,
    ResearchRun,
    SourceDocument,
)
from atlas.research.schemas import ClaimScope
from atlas.research.verification import canonical
from atlas.schemas import Fact, FactKey, OpportunityInput, Source, StrictModel
from atlas.services.storage import insert, update_fact

MAPPING = {
    "tuition_funding": FactKey.tuition,
    "living_stipend": FactKey.stipend,
    "deadline": FactKey.deadline,
    "application_fee": FactKey.application_fee,
    "proof_of_funds": FactKey.proof_of_funds,
    "eligibility": FactKey.eligibility_conditions,
    "language": FactKey.language_requirements,
    "scholarship_obligations": FactKey.scholarship_obligations,
}


class RecordIdentity(StrictModel):
    external_id: str = Field(min_length=1, max_length=120, pattern=r"^[\w.-]+$")
    title: str = Field(min_length=3, max_length=200)
    institution: str = Field(min_length=2, max_length=200)
    country: str = Field(min_length=2, max_length=80)
    summary: str = Field(min_length=10, max_length=5000)


class ProposalInput(StrictModel):
    scope: ClaimScope
    identity: RecordIdentity | None = None
    target_opportunity_id: int | None = Field(default=None, ge=1)
    expected_opportunity_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def explicit_target(self) -> "ProposalInput":
        if self.target_opportunity_id is None and self.identity is None:
            raise ValueError("A new record requires reviewed identity metadata")
        if self.target_opportunity_id and not self.expected_opportunity_revision:
            raise ValueError("An update requires the exact opportunity revision you inspected")
        return self


class ProposalApproval(StrictModel):
    expected_revision: int = Field(ge=1)
    selected_fields: list[FactKey] = Field(min_length=1, max_length=20)
    actor: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=5, max_length=1500)
    confirm_source_review: Literal[True]


def same_scope(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return ClaimScope.model_validate(left) == ClaimScope.model_validate(right)


def claim_material(session: Session, claim: ExtractedClaim) -> dict[str, Any]:
    support = session.get(EvidenceSnippet, claim.evidence_id) if claim.evidence_id else None
    scope = (
        session.get(EvidenceSnippet, claim.scope_evidence_id) if claim.scope_evidence_id else None
    )
    doc = session.get(SourceDocument, claim.document_id)
    if (
        not doc
        or not support
        or not scope
        or any(
            e.run_id != claim.run_id
            or e.document_id != doc.id
            or doc.text[e.start : e.end] != e.quote
            for e in (support, scope)
        )
    ):
        raise HTTPException(409, "Original evidence is missing or no longer resolves")
    if claim.state not in {"source_supported", "corroborated"} or (
        claim.semantic_assessment.get("label") != "fully_supported"
    ):
        raise HTTPException(409, "Finding requires semantic/context review or has a conflict")
    return {
        "claim_id": claim.id,
        "document_id": doc.id,
        "field": claim.field,
        "value": claim.value,
        "scope": claim.scope,
        "evidence_id": support.id,
        "scope_evidence_id": scope.id,
        "quote": support.quote,
        "scope_quote": scope.quote,
        "url": doc.url,
        "source_hash": doc.sha256,
        "retrieved_at": utc_iso(doc.fetched_at),
        "synthetic": doc.synthetic,
        "semantic_assessment": claim.semantic_assessment,
    }


def propose(session: Session, run: ResearchRun, data: ProposalInput) -> ResearchProposal:
    if run.status in {"pending", "running"}:
        raise HTTPException(409, "Wait for the final or partial report before proposing changes")
    target = (
        session.get(Opportunity, data.target_opportunity_id) if data.target_opportunity_id else None
    )
    if data.target_opportunity_id and not target:
        raise HTTPException(404, "Target opportunity not found")
    if target and target.revision != data.expected_opportunity_revision:
        raise HTTPException(409, "Opportunity changed; reload and inspect its current revision")
    claims = [
        c
        for c in session.scalars(select(ExtractedClaim).where(ExtractedClaim.run_id == run.id))
        if same_scope(c.scope, data.scope.model_dump())
    ]
    materials = []
    blocked = []
    for claim in claims:
        if claim.field not in MAPPING:
            continue
        try:
            materials.append(claim_material(session, claim))
        except HTTPException:
            blocked.append(
                {
                    "field": claim.field,
                    "claim_id": claim.id,
                    "reason": "Unsupported, conflicting or incompletely reviewed evidence",
                }
            )
    synthetic = run.mode == "demo" or any(m["synthetic"] for m in materials)
    if target and synthetic and not target.payload.get("synthetic"):
        raise HTTPException(409, "Synthetic research cannot modify a real opportunity")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for material in materials:
        field = str(MAPPING[material["field"]])
        grouped.setdefault(field, []).append(material)
    changes = []
    for field, items in grouped.items():
        values = {item["value"] for item in items}
        if len(values) != 1:
            blocked.append(
                {"field": field, "reason": "Multiple values require manual reconciliation"}
            )
            continue
        item = items[0]
        value = item["value"]
        if field == "proof_of_funds":
            normalized = canonical("proof_of_funds", value)
            if normalized not in {"required", "not_required"}:
                blocked.append(
                    {"field": field, "reason": "Conditional financial rule needs manual review"}
                )
                continue
            value = "yes" if normalized == "required" else "no"
        if field == "deadline" and canonical("deadline", value) is None:
            blocked.append({"field": field, "reason": "Directory requires an unambiguous ISO date"})
            continue
        fact = Fact(
            value=value,
            state="unverified",
            source_id="r-" + item["document_id"],
            excerpt=item["quote"],
        ).model_dump(mode="json")
        changes.append(
            {
                "field": field,
                "before": target.payload["facts"].get(field) if target else None,
                "after": fact,
                "claim_ids": [i["claim_id"] for i in items],
                "evidence": items,
            }
        )
    if not changes:
        raise HTTPException(409, "No conflict-free supported findings are available for this scope")
    proposal = ResearchProposal(
        run_id=run.id,
        target_opportunity_id=data.target_opportunity_id,
        expected_opportunity_revision=data.expected_opportunity_revision,
        content={
            "scope": data.scope.model_dump(mode="json"),
            "identity": data.identity.model_dump(mode="json") if data.identity else None,
            "synthetic": synthetic,
            "changes": changes,
            "blocked": blocked,
        },
    )
    session.add(proposal)
    session.commit()
    return proposal


def approve(
    session: Session, proposal: ResearchProposal, data: ProposalApproval
) -> ResearchProposal:
    if proposal.status != "pending" or proposal.revision != data.expected_revision:
        raise HTTPException(409, "Proposal already reviewed or changed; reload before approving")
    selected = set(data.selected_fields)
    available = {change["field"] for change in proposal.content["changes"]}
    if not selected <= available:
        raise HTTPException(422, "Selected fields must be present in this proposal")
    changes = [c for c in proposal.content["changes"] if c["field"] in selected]
    sources: dict[str, dict[str, Any]] = {}
    facts = {}
    for change in changes:
        for item in change["evidence"]:
            claim = session.get(ExtractedClaim, item["claim_id"])
            if (
                not claim
                or claim.run_id != proposal.run_id
                or claim_material(session, claim) != item
            ):
                raise HTTPException(409, "Evidence changed; create a fresh proposal")
        material = change["evidence"][0]
        source_id = "r-" + material["document_id"]
        sources[source_id] = Source(
            id=source_id,
            label="Human-reviewed research source",
            url=material["url"],
            kind="demo" if material["synthetic"] else "official_url",
            retrieved_at=date.fromisoformat(material["retrieved_at"][:10]),
            content_sha256=material["source_hash"],
            official_asserted=False,
        ).model_dump(mode="json")
        facts[change["field"]] = {**change["after"], "state": "verified"}
    reason = f"Research proposal {proposal.id}: {data.reason}"
    if proposal.target_opportunity_id:
        row = session.get(Opportunity, proposal.target_opportunity_id)
        if not row or row.revision != proposal.expected_opportunity_revision:
            raise HTTPException(
                409, "Opportunity changed since the proposal; inspect a fresh proposal"
            )
        if proposal.content["synthetic"] and not row.payload.get("synthetic"):
            raise HTTPException(409, "Synthetic research cannot modify a real opportunity")
        payload = {**row.payload, "facts": {**row.payload["facts"], **facts}}
        existing = {s["id"] for s in row.payload["sources"]}
        payload["sources"] = [
            *row.payload["sources"],
            *[s for k, s in sources.items() if k not in existing],
        ]
        validated = OpportunityInput.model_validate(payload)
        update_fact(
            session, row, validated.model_dump(mode="json"), data.actor, reason, commit=False
        )
    else:
        identity = proposal.content["identity"]
        validated = OpportunityInput.model_validate(
            {
                **identity,
                "synthetic": proposal.content["synthetic"],
                "facts": facts,
                "sources": list(sources.values()),
            }
        )
        row = insert(session, validated)
        change_row = session.scalar(select(Change).where(Change.opportunity_id == row.id))
        assert change_row
        change_row.actor, change_row.reason = data.actor, reason
    proposal.status, proposal.reviewed_at = "approved", utcnow()
    proposal.approval = {
        "actor": data.actor,
        "reason": data.reason,
        "selected_fields": sorted(selected),
        "confirm_source_review": True,
        "opportunity_id": row.id,
        "opportunity_revision": row.revision,
    }
    session.commit()
    return proposal


def proposal_dict(row: ResearchProposal) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "status": row.status,
        "revision": row.revision,
        "target_opportunity_id": row.target_opportunity_id,
        "expected_opportunity_revision": row.expected_opportunity_revision,
        "content": row.content,
        "approval": row.approval,
        "created_at": utc_iso(row.created_at),
        "reviewed_at": utc_iso(row.reviewed_at) if row.reviewed_at else None,
    }
