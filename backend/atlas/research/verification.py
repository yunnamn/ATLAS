"""Citation checks and deliberately conservative comparisons, independent of the model."""

import re
from datetime import date
from decimal import Decimal
from itertools import combinations
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.research.models import (
    Contradiction,
    EvidenceSnippet,
    ExtractedClaim,
    ResearchRun,
    SourceDocument,
)
from atlas.research.semantics import (
    assess_support,
    context_scope_valid,
    requested_year,
    scope_relation,
)

SUPPORTED = {"source_supported", "corroborated", "contradictory"}


def exact_span(text: str, quote: str, start: int | None = None) -> tuple[int, int] | None:
    if not quote or (start is not None and start < 0):
        return None
    if start is not None:
        return (start, start + len(quote)) if text[start : start + len(quote)] == quote else None
    first = text.find(quote)
    if first < 0 or text.find(quote, first + 1) >= 0:
        return None
    return first, first + len(quote)


def canonical(field: str, value: str) -> str | None:
    text = value.strip().casefold()
    if field == "tuition_funding":
        if text in {"full tuition", "tuition fully covered", "tuition waived"}:
            return "covered"
        if text in {"tuition not covered", "no tuition funding", "tuition not waived"}:
            return "not_covered"
    if field == "proof_of_funds":
        if text in {"required", "proof of funds required", "bank statement required"}:
            return "required"
        if text in {"not required", "proof of funds not required", "no bank statement required"}:
            return "not_required"
    if field == "deadline" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    if field == "application_fee":
        match = re.fullmatch(r"(\d+(?:\.\d+)?) ([A-Z]{3})", value)
        if match:
            return f"{match[2]}:{Decimal(match[1]).normalize()}"
    return None


def snippet(
    session: Session,
    claim: ExtractedClaim,
    doc: SourceDocument,
    span: tuple[int, int],
    purpose: str,
) -> EvidenceSnippet:
    location = next(
        (part for part in doc.locations if part["start"] <= span[0] and span[1] <= part["end"]), {}
    )
    evidence = EvidenceSnippet(
        run_id=claim.run_id,
        document_id=doc.id,
        start=span[0],
        end=span[1],
        quote=doc.text[span[0] : span[1]],
        location=location,
        purpose=purpose,
    )
    session.add(evidence)
    session.flush()
    return evidence


def verify_claims(session: Session, run: ResearchRun) -> dict[str, int]:
    claims = list(session.scalars(select(ExtractedClaim).where(ExtractedClaim.run_id == run.id)))
    for claim in claims:
        if claim.evidence_id:
            continue
        doc = session.get(SourceDocument, claim.document_id)
        assert doc is not None
        support = exact_span(doc.text, claim.proposed_quote, claim.proposed_start)
        scope = exact_span(doc.text, claim.proposed_scope_quote)
        scope_ok = claim.scope["program"] in claim.proposed_scope_quote and (
            claim.scope.get("intake_year") is None
            or str(claim.scope["intake_year"]) in claim.proposed_scope_quote
        )
        scope_ok = bool(scope and scope_ok) and all(
            not claim.scope.get(key) or claim.scope[key] in claim.proposed_scope_quote
            for key in ("award_track", "applicant_group", "source_version")
        )
        scope_ok = scope_ok and context_scope_valid(doc.text, support, claim.scope)
        assessment = assess_support(
            claim.field,
            claim.value,
            claim.proposed_quote,
            doc.text,
            support,
            scope_ok,
            claim.scope,
            requested_year(run.objective, run.request.get("target_intake_year")),
        )
        claim.semantic_assessment = assessment
        # Preserve valid spans even when the meaning fails screening; never conflate the two.
        if support:
            claim.evidence_id = snippet(session, claim, doc, support, "support").id
        if scope:
            claim.scope_evidence_id = snippet(session, claim, doc, scope, "scope").id
        claim.verification_note = assessment["reason"] + ": " + assessment["resolution"]
        if assessment["label"] != "fully_supported":
            continue
        claim.state = "source_supported"
        claim.normalized_value = canonical(claim.field, claim.value)
    session.flush()
    supported = [c for c in claims if c.state in SUPPORTED]
    groups = run.request.get("source_groups", {})
    for left, right in combinations(supported, 2):
        # Do not compare different intakes, unscoped claims or different programs.
        if left.field != right.field:
            continue
        doc_a, doc_b = (
            session.get(SourceDocument, left.document_id),
            session.get(SourceDocument, right.document_id),
        )
        assert doc_a and doc_b
        relation = scope_relation(
            left.scope,
            right.scope,
            same_url_version_change=doc_a.url == doc_b.url and doc_a.sha256 != doc_b.sha256,
        )
        if relation != "same_scope":
            continue
        a, b = left.normalized_value, right.normalized_value
        if a is not None and b is not None and a != b:
            if left.field == "application_fee" and a.split(":")[0] != b.split(":")[0]:
                continue  # Different currencies are not compared or converted.
            existing = session.scalar(
                select(Contradiction).where(
                    Contradiction.run_id == run.id,
                    Contradiction.left_claim_id == left.id,
                    Contradiction.right_claim_id == right.id,
                )
            )
            if not existing:
                session.add(
                    Contradiction(
                        run_id=run.id,
                        left_claim_id=left.id,
                        right_claim_id=right.id,
                        field=left.field,
                        summary=f"Conflicting recorded {left.field.replace('_', ' ')} "
                        "values for the same program/intake; investigate context",
                    )
                )
            left.state = right.state = "contradictory"
        elif (a is not None and a == b) or left.value == right.value:
            group_a, group_b = (
                groups.get(urlsplit(doc_a.url).hostname),
                groups.get(urlsplit(doc_b.url).hostname),
            )
            if group_a and group_b and group_a != group_b and doc_a.sha256 != doc_b.sha256:
                # Independence is a caller assertion; never inferred from LLM agreement.
                for claim in (left, right):
                    if claim.state != "contradictory":
                        claim.state = "corroborated"
    session.flush()
    return {
        "supported": sum(c.state in SUPPORTED for c in claims),
        "unverified": sum(c.state == "unverified" for c in claims),
        "contradictory": sum(c.state == "contradictory" for c in claims),
    }


def evidence_dict(e: EvidenceSnippet, document: SourceDocument) -> dict[str, Any]:
    return {
        "id": e.id,
        "document_id": e.document_id,
        "quote": e.quote,
        "start": e.start,
        "end": e.end,
        "location": e.location,
        "purpose": e.purpose,
        "url": document.url,
        "source_hash": document.sha256,
        "synthetic": document.synthetic,
    }
