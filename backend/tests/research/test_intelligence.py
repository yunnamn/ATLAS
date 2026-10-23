import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from atlas.config import Settings
from atlas.research.demo import DEMO_SEED, DemoFetcher, DemoProvider
from atlas.research.engine import ResearchEngine
from atlas.research.intelligence import pack_observations, prioritize, temporal_warnings
from atlas.research.models import ExtractedClaim, ResearchCandidate, ResearchReport, ResearchRun
from atlas.research.semantics import assess_support, context_scope_valid, scope_relation
from atlas.research.verification import exact_span
from tests.research.helpers import make_run

CASES = json.loads(Path("atlas/research/fixtures/semantic-cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_adversarial_meaning_controls(case) -> None:
    result = assess_support(
        case["field"],
        case["value"],
        case["quote"],
        case["text"],
        exact_span(case["text"], case["quote"]),
        case.get("scope_valid", True),
        {"program": "Synthetic MSc", "intake_year": case.get("intake_year", 2027)},
        case.get("target_year"),
    )
    assert result["label"] == case["expected"]
    assert result["resolution"] and not result["independent_ground_truth"]


@pytest.mark.parametrize(
    ("change", "relation"),
    [
        ({"intake_year": 2026}, "different_intake"),
        ({"award_track": "merit award"}, "different_award_track"),
        ({"applicant_group": "domestic applicants"}, "different_applicant_group"),
        ({"source_version": "2027 revised edition"}, "different_source_version"),
        ({"award_track": None}, "incomplete_scope"),
        ({"source_version": None}, "incomplete_scope"),
    ],
)
def test_scope_dimensions_do_not_become_false_contradictions(change, relation) -> None:
    left = {
        "program": "Synthetic MSc",
        "intake_year": 2027,
        "award_track": "need award",
        "applicant_group": "international applicants",
        "source_version": "2027 edition",
    }
    assert scope_relation(left, {**left, **change}) == relation
    assert scope_relation(left, left, same_url_version_change=True) == "different_source_version"


def test_priority_explains_requested_intake_and_relevance_not_domain_truth() -> None:
    candidates = [
        ResearchCandidate(
            id="old", url="https://approved.edu/funding-2026", title="Funding 2026", origin="search"
        ),
        ResearchCandidate(
            id="new", url="https://approved.edu/funding-2027", title="Funding 2027", origin="search"
        ),
    ]
    ranked = prioritize(candidates, "Investigate scholarship funding in 2027", None)
    assert ranked[0]["id"] == "new"
    assert any("not authenticated" in r for r in ranked[0]["priority_reasons"])


def test_failed_semantics_keeps_exact_citation_but_not_a_report_finding(sessions) -> None:
    class Misleading(DemoProvider):
        def generate(self, output, task, payload, budget):
            result = super().generate(output, task, payload, budget)
            if task == "EXTRACT":
                for claim in result.claims:
                    if claim.field == "tuition_funding":
                        claim.field = "living_stipend"
            return result

    run_id = make_run(sessions)
    ResearchEngine(sessions, run_id, Misleading(), DemoFetcher("funding_gap"), Settings()).execute()
    with sessions() as s:
        claims = list(s.scalars(select(ExtractedClaim).where(ExtractedClaim.run_id == run_id)))
        rejected = [c for c in claims if c.value == "full tuition"]
        assert rejected and all(c.evidence_id and c.state == "unverified" for c in rejected)
        report = s.get(ResearchReport, run_id).content
        assert not any(c["value"] == "full tuition" for c in report["findings"])
        assert any(q["status"] == "needs_investigation" for q in report["question_assessments"])


def test_identical_content_at_another_url_does_not_trigger_redundant_extraction(sessions) -> None:
    class Duplicate(DemoFetcher):
        def fetch(self, url, budget):
            document = super().fetch(DEMO_SEED, budget)
            document.url = url
            return document

    run_id = make_run(sessions)
    ResearchEngine(sessions, run_id, DemoProvider(), Duplicate("funding_gap"), Settings()).execute()
    with sessions() as s:
        run = s.get(ResearchRun, run_id)
        assert run.status == "completed"
        assert run.stats["provider_requests"] == 5
        report = s.get(ResearchReport, run_id).content
        assert len(report["sources"]) == 2 and report["outcome"] == "partial"


def test_exact_quote_from_another_program_section_does_not_inherit_the_wrong_header() -> None:
    text = "Alpha Master's — 2027\nTuition: partial\nBeta Master's — 2027\nTuition: full tuition"
    span = exact_span(text, "Tuition: full tuition")
    assert not context_scope_valid(text, span, {"program": "Alpha Master's", "intake_year": 2027})
    assert context_scope_valid(text, span, {"program": "Beta Master's", "intake_year": 2027})


def test_exact_quote_from_an_older_heading_does_not_inherit_current_intake() -> None:
    text = "Alpha Master's — 2026\nProgram: Alpha Master's\nTuition: full tuition"
    span = exact_span(text, "Tuition: full tuition")
    assert not context_scope_valid(text, span, {"program": "Alpha Master's", "intake_year": 2027})


def test_past_deadline_is_an_advisory_not_a_fabricated_new_date() -> None:
    claim = ExtractedClaim(id="past", field="deadline", value="2026-01-01")
    warnings = temporal_warnings([claim], date(2026, 10, 23))
    assert warnings[0]["value"] == "2026-01-01"
    assert warnings[0]["as_of_date"] == "2026-10-23"
    assert claim.value == "2026-01-01"


def test_repeated_search_is_observable_but_dispatched_only_once(sessions) -> None:
    from atlas.research.schemas import Decision

    class Repeat(DemoProvider):
        def generate(self, output, task, payload, budget):
            if task == "DECIDE":
                budget.model_request(1000, live=False)
                return Decision(
                    action="search", query="  Funding   2027 ", summary="Inspect funding sources"
                )
            return super().generate(output, task, payload, budget)

    class Search:
        calls = 0

        def search(self, query, budget):
            self.calls += 1
            return []

    run_id = make_run(sessions)
    search = Search()
    ResearchEngine(
        sessions, run_id, Repeat(), DemoFetcher("funding_gap"), Settings(), search
    ).execute()
    with sessions() as s:
        run = s.get(ResearchRun, run_id)
        assert run.stop_reason == "iterations" and run.status == "completed"
        assert run.stats["tool_calls"] == 1 and search.calls == 1


def test_identical_reextraction_focus_and_window_is_not_dispatched(sessions) -> None:
    from atlas.research.schemas import Decision

    class Repeat(DemoProvider):
        def generate(self, output, task, payload, budget):
            if task == "DECIDE" and payload["observations"]["document_count"]:
                budget.model_request(1000, live=False)
                previous = payload["observations"]["extracted_windows"][0]
                return Decision(
                    action="reextract",
                    target_id=previous["document_id"],
                    question_id=previous["question_id"],
                    summary="Repeat the same document focus",
                )
            return super().generate(output, task, payload, budget)

    run_id = make_run(sessions)
    ResearchEngine(sessions, run_id, Repeat(), DemoFetcher("funding_gap"), Settings()).execute()
    with sessions() as s:
        run = s.get(ResearchRun, run_id)
        assert run.stop_reason == "iterations" and run.stats["tool_calls"] == 1


def test_packing_limits_model_context_but_preserves_full_validation_ledger() -> None:
    original = {
        "claims": [{"value": "x" * 1000} for _ in range(120)],
        "candidates": [
            {"id": str(i), "url": "https://example.edu/" + "x" * 1000} for i in range(40)
        ],
        "missing_fields": ["proof_of_funds"],
        "available_actions": ["fetch", "stop"],
        "previous_queries": [f"query {i}" for i in range(12)],
        "stats": {"provider_requests": 3},
    }
    packed = pack_observations(dict(original))
    assert len(json.dumps(packed)) <= 24000 and packed["context_truncated"]
    assert packed["collection_totals"]["claims"] == 120
    assert packed["missing_fields"] == ["proof_of_funds"]
    assert packed["stats"] == original["stats"]
    assert len(original["claims"]) == 120 and len(original["previous_queries"]) == 12
