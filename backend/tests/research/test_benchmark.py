from copy import deepcopy

import pytest
from pydantic import ValidationError

from atlas.config import Settings
from atlas.research.benchmark import (
    APPROACHES,
    Corpus,
    ReferenceLabels,
    load_documents,
    measure,
    run_case,
    synthetic_corpus,
)
from atlas.research.demo import DemoProvider


def test_abc_comparison_is_reproducible_and_does_not_claim_agent_superiority() -> None:
    corpus, root = synthetic_corpus()
    case = corpus.cases[0]
    docs = load_documents(case, root, True)
    rows = [
        run_case(case, docs, approach, DemoProvider(), Settings(), True) for approach in APPROACHES
    ]
    assert [r["metrics"]["correct_claims"] for r in rows] == [9, 14, 14]
    assert [r["provider_requests"] for r in rows] == [1, 2, 6]
    assert [r["tool_calls"] for r in rows] == [1, 2, 2]
    assert all(r["actual_model_requests"] == 0 and r["input_tokens"] is None for r in rows)
    assert all(r["estimated_model_cost_usd"] == 0 for r in rows)
    assert all(r["metrics"]["citation_correctness"] == 1 for r in rows)
    assert not rows[0]["metrics"]["task_success"] and rows[2]["metrics"]["task_success"]


def test_unannotated_authentic_quality_is_withheld_rather_than_manufactured() -> None:
    corpus, root = synthetic_corpus()
    case = corpus.cases[0].model_copy(update={"labels": None})
    result = run_case(
        case, load_documents(case, root, False), "A_direct", DemoProvider(), Settings(), False
    )
    assert not result["quality_scores_available"]
    assert result["metrics"]["extraction_precision"] is None
    assert result["metrics"]["unsupported_claim_rate"] is None
    assert result["metrics"]["task_success"] is None


def test_single_author_does_not_count_as_independent_ground_truth() -> None:
    corpus, _ = synthetic_corpus()
    labels = corpus.cases[0].labels.model_dump()
    labels["status"] = "independently_reviewed"
    with pytest.raises(ValidationError, match="two distinct"):
        ReferenceLabels.model_validate(labels)
    labels["annotators"] = ["", "Reviewer"]
    with pytest.raises(ValidationError, match="nonempty"):
        ReferenceLabels.model_validate(labels)


def test_one_explicit_case_cannot_select_multiple_costly_experiments() -> None:
    corpus, _ = synthetic_corpus()
    data = corpus.model_dump()
    data["cases"] = [data["cases"][0], data["cases"][0]]
    with pytest.raises(ValidationError, match="Case IDs must be unique"):
        Corpus.model_validate(data)


def test_corpus_refuses_modified_documents_and_path_escape(tmp_path) -> None:
    corpus, root = synthetic_corpus()
    case = deepcopy(corpus.cases[0])
    case.documents[0].sha256 = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        load_documents(case, root, True)
    case.documents[0].path = "../outside.html"
    with pytest.raises(ValueError, match="inside the manifest"):
        load_documents(case, root, True)


def test_scope_is_part_of_reference_identity_even_when_value_and_url_match() -> None:
    corpus, root = synthetic_corpus()
    case = corpus.cases[0]
    doc = case.documents[0]
    claim = case.labels.claims[0]
    snippets = [
        {
            "id": "e1",
            "url": doc.url,
            "start": 0,
            "end": 0,
            "quote": "",
        }
    ]
    report = {
        "evidence": snippets,
        "findings": [
            {
                "field": claim.field,
                "value": claim.value,
                "scope": {**claim.scope.model_dump(), "applicant_group": "different applicants"},
                "evidence_id": "e1",
                "scope_evidence_id": "e1",
            }
        ],
        "unanswered_questions": [],
        "conflicts": [],
    }
    result = measure(case, report, load_documents(case, root, True), True)
    assert result["extraction_precision"] == 0 and result["unsupported_claim_rate"] == 1
    assert result["citation_correctness"] == 0
