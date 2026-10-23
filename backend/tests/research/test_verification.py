from copy import deepcopy

import pytest
from sqlalchemy import select

from atlas.config import Settings
from atlas.research.demo import DemoFetcher, DemoProvider
from atlas.research.engine import ResearchEngine
from atlas.research.models import ExtractedClaim, ResearchRun
from atlas.research.verification import canonical, exact_span, verify_claims
from tests.research.helpers import make_run


def test_exact_spans_reject_ambiguous_or_fabricated_quotations() -> None:
    assert exact_span("Evidence here", "Evidence") == (0, 8)
    assert exact_span("same same", "same") is None
    assert exact_span("same same", "same", 5) == (5, 9)
    assert exact_span("same same", "same", 2) is None
    assert exact_span("evidence", "invented") is None


@pytest.mark.parametrize(
    ("field", "value", "normalized"),
    [
        ("tuition_funding", "full tuition", "covered"),
        ("tuition_funding", "might receive full tuition", None),
        ("proof_of_funds", "not required", "not_required"),
        ("proof_of_funds", "may be required", None),
        ("deadline", "2027-02-30", None),
        ("deadline", "2027-02-15", "2027-02-15"),
    ],
)
def test_conservative_normalization(field, value, normalized) -> None:
    assert canonical(field, value) == normalized


def test_corroboration_requires_explicit_authority_groups_and_not_model_agreement(sessions) -> None:
    run_id = make_run(sessions)
    ResearchEngine(
        sessions, run_id, DemoProvider(), DemoFetcher("funding_gap"), Settings()
    ).execute()
    with sessions() as s:
        run = s.get(ResearchRun, run_id)
        claims = list(
            s.scalars(
                select(ExtractedClaim).where(
                    ExtractedClaim.run_id == run_id, ExtractedClaim.field == "tuition_funding"
                )
            )
        )
        assert len(claims) == 2 and {c.state for c in claims} == {"source_supported"}
        run.request = {
            **run.request,
            "source_groups": {
                "lumen.atlas.invalid": "institution",
                "fund.atlas.invalid": "independent-funder",
            },
        }
        verify_claims(s, run)
        s.commit()
        assert {c.state for c in claims} == {"corroborated"}


def test_different_intakes_do_not_create_false_conflicts(sessions) -> None:
    run_id = make_run(sessions, demo_scenario="conflict")
    ResearchEngine(sessions, run_id, DemoProvider(), DemoFetcher("conflict"), Settings()).execute()
    with sessions() as s:
        claims = list(
            s.scalars(
                select(ExtractedClaim).where(
                    ExtractedClaim.run_id == run_id, ExtractedClaim.field == "tuition_funding"
                )
            )
        )
        # Test the comparison on two already-supported historical scopes in an isolated new run.
        other_id = make_run(sessions)
        for index, original in enumerate(claims):
            copy = ExtractedClaim(
                run_id=other_id,
                document_id=original.document_id,
                field=original.field,
                value=original.value,
                scope={**deepcopy(original.scope), "intake_year": 2026 + index},
                proposed_quote=original.proposed_quote,
                proposed_scope_quote=original.proposed_scope_quote,
                evidence_id=original.evidence_id,
                scope_evidence_id=original.scope_evidence_id,
                normalized_value=original.normalized_value,
                state="source_supported",
            )
            s.add(copy)
        s.commit()
        verify_claims(s, s.get(ResearchRun, other_id))
        assert all(
            c.state == "source_supported"
            for c in s.scalars(select(ExtractedClaim).where(ExtractedClaim.run_id == other_id))
        )
