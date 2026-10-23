"""Observable evidence gaps and source priority, independent of model agreement."""

import json
import re
from datetime import date
from itertools import combinations
from typing import Any

from atlas.research.models import ExtractedClaim, ResearchCandidate, ResearchPlan, SourceDocument
from atlas.research.semantics import requested_year, scope_relation


def pack_observations(data: dict[str, Any], limit: int = 24000) -> dict[str, Any]:
    """Bound decision context while making every omitted collection count observable."""
    arrays = [key for key, value in data.items() if isinstance(value, list)]
    data["collection_totals"] = {key: len(data[key]) for key in arrays}
    data["context_truncated"] = False
    # Keep budgets, actions, aggregate gaps and the latest failure feedback.
    removable = [
        "claims",
        "evidence_assessments",
        "context_differences",
        "question_assessments",
        "temporal_warnings",
        "failed_sources",
        "extracted_windows",
        "previous_queries",
        "candidates",
        "documents",
    ]
    removable = [key for key in removable if key in data]
    while len(json.dumps(data)) > limit:
        if not removable:
            break
        key = max(removable, key=lambda k: len(json.dumps(data[k])) if len(data[k]) > 1 else 0)
        if len(data[key]) <= 1:
            break
        data[key] = data[key][: max(1, len(data[key]) // 2)]
        data["context_truncated"] = True
    return data


def prioritize(
    candidates: list[ResearchCandidate], objective: str, target_year: int | None
) -> list[dict[str, Any]]:
    words = set(re.findall(r"[a-z]{4,}", objective.casefold()))
    year = requested_year(objective, target_year)
    ranked = []
    for candidate in candidates:
        text = (candidate.title + " " + candidate.url).casefold()
        score, reasons = 0, ["Within caller-approved domain scope; authority is not authenticated"]
        if candidate.origin == "seed":
            score += 30
            reasons.append("Explicitly supplied starting source")
        overlap = words & set(re.findall(r"[a-z]{4,}", text))
        score += min(20, 4 * len(overlap))
        if overlap:
            reasons.append("Objective vocabulary overlaps title or URL")
        if re.search(r"scholarship|admission|handbook|funding|eligibility", text):
            score += 10
            reasons.append("Direct requirements or funding document indicator")
        years = {int(y) for y in re.findall(r"\b20[2-9][0-9]\b", text)}
        if year and year in years:
            score += 15
            reasons.append("Requested intake appears in title or URL")
        elif year and years and max(years) < year:
            score -= 30
            reasons.append("Title or URL appears to describe an older intake; verify applicability")
        ranked.append(
            {
                "id": candidate.id,
                "url": candidate.url,
                "title": candidate.title,
                "origin": candidate.origin,
                "priority": score,
                "priority_reasons": reasons,
            }
        )
    return sorted(ranked, key=lambda c: (-c["priority"], c["url"]))


def question_sufficiency(
    plans: list[ResearchPlan],
    supported: list[ExtractedClaim],
    scopes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not plans:
        return []
    assessments = []
    scope_options: list[dict[str, Any] | None] = list(scopes) if scopes else [None]
    for scope in scope_options:
        for question in plans[-1].content["questions"]:
            answers = [c for c in supported if scope is None or c.scope == scope]
            fields = []
            for field in question["fields"]:
                matches = [c for c in answers if c.field == field]
                conflict = any(c.state == "contradictory" for c in matches)
                legacy = any(not c.semantic_assessment for c in matches)
                state = (
                    "conflicting"
                    if conflict
                    else (
                        "needs_semantic_review" if legacy else "supported" if matches else "unknown"
                    )
                )
                fields.append(
                    {
                        "field": field,
                        "status": state,
                        "claim_ids": [c.id for c in matches],
                        "resolution": "Inspect the cited evidence and its applicability."
                        if state == "supported"
                        else "Obtain current scoped evidence or record this gap as unresolved.",
                    }
                )
            complete = all(f["status"] == "supported" for f in fields)
            assessments.append(
                {
                    "question_id": question["id"],
                    "question": question["question"],
                    "scope": scope,
                    "status": "supported" if complete else "needs_investigation",
                    "fields": fields,
                    "criterion_evaluation": "field_coverage_only; prose criteria need human review",
                }
            )
    return assessments


def contextual_differences(
    claims: list[ExtractedClaim],
    documents: dict[str, SourceDocument],
) -> list[dict[str, Any]]:
    results = []
    for left, right in combinations(claims, 2):
        if (
            left.field != right.field
            or left.value == right.value
            or not (left.evidence_id and right.evidence_id)
        ):
            continue
        a, b = documents.get(left.document_id), documents.get(right.document_id)
        relation = scope_relation(
            left.scope,
            right.scope,
            same_url_version_change=bool(a and b and a.url == b.url and a.sha256 != b.sha256),
        )
        if relation not in ("same_scope", "different_program"):
            results.append(
                {
                    "field": left.field,
                    "claim_ids": [left.id, right.id],
                    "relation": relation,
                    "resolution": "Compare source dates, applicant/award conditions and versions; "
                    "no source is automatically preferred as truth.",
                }
            )
    return results


def temporal_warnings(claims: list[ExtractedClaim], investigated_on: date) -> list[dict[str, Any]]:
    warnings = []
    for claim in claims:
        if claim.field != "deadline":
            continue
        try:
            deadline = date.fromisoformat(claim.value)
        except ValueError:
            continue
        if deadline < investigated_on:
            warnings.append(
                {
                    "claim_id": claim.id,
                    "field": claim.field,
                    "value": claim.value,
                    "warning": "Deadline predates this investigation; check current intake dates.",
                    "as_of_date": investigated_on.isoformat(),
                }
            )
    return warnings
