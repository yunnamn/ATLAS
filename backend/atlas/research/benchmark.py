"""Frozen-document A/B/C experiments. No live inference without an explicit CLI opt-in."""

import argparse
import hashlib
import json
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from atlas.config import Settings
from atlas.db import Base, utc_iso, utcnow
from atlas.research.budget import Budget
from atlas.research.demo import DEMO_AWARD, DEMO_OBJECTIVE, DEMO_SEED, DemoProvider
from atlas.research.documents import DocumentContent, normalize_document
from atlas.research.engine import ResearchEngine
from atlas.research.errors import ResearchError
from atlas.research.fetcher import SafeFetcher
from atlas.research.models import ExtractedClaim, ResearchReport, ResearchRun, ResearchStep
from atlas.research.network import URLPolicy
from atlas.research.providers import ModelProvider, OpenAICompatibleProvider
from atlas.research.schemas import (
    ClaimScope,
    Decision,
    PlanSpec,
    ResearchField,
    RunInput,
    RunLimits,
)
from atlas.research.semantics import assess_support
from atlas.research.verification import exact_span
from atlas.schemas import StrictModel

T = TypeVar("T", bound=BaseModel)
APPROACHES = ("A_direct", "B_fixed_retrieval", "C_adaptive")


class CorpusDocument(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    url: str = Field(max_length=2000)
    path: str = Field(max_length=1000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: Literal["text/html", "application/pdf"]
    retrieved_at: str = Field(max_length=50)
    source_owner: str = Field(min_length=2, max_length=200)
    reuse_note: str = Field(min_length=10, max_length=1000)


class ReferenceClaim(StrictModel):
    document_id: str
    field: ResearchField
    value: str = Field(min_length=1, max_length=1000)
    scope: ClaimScope
    support_quote: str = Field(min_length=3, max_length=3000)


class ReferenceLabels(StrictModel):
    status: Literal["author_labeled", "independently_reviewed"]
    annotators: list[str] = Field(min_length=1, max_length=5)
    claims: list[ReferenceClaim] = Field(max_length=200)
    unknown_fields: list[ResearchField] = Field(max_length=12)
    conflict_fields: list[ResearchField] = Field(max_length=12)
    annotation_notes: str = Field(min_length=10, max_length=2000)

    @field_validator("annotators")
    @classmethod
    def reviewer_names(cls, names: list[str]) -> list[str]:
        if any(not name.strip() or len(name) > 100 for name in names):
            raise ValueError("Reviewers require nonempty names of at most 100 characters")
        return [name.strip() for name in names]

    @model_validator(mode="after")
    def independent_review(self) -> "ReferenceLabels":
        if self.status == "independently_reviewed" and len(set(self.annotators)) < 2:
            raise ValueError("Independent labels require at least two distinct named reviewers")
        return self


class BenchmarkCase(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    objective: str = Field(min_length=20, max_length=4000)
    documents: list[CorpusDocument] = Field(min_length=1, max_length=8)
    supplied_document_id: str
    retrieval_document_ids: list[str] = Field(min_length=1, max_length=8)
    plan: PlanSpec
    labels: ReferenceLabels | None = None

    @model_validator(mode="after")
    def references(self) -> "BenchmarkCase":
        ids = [d.id for d in self.documents]
        if len(ids) != len(set(ids)) or len({d.url for d in self.documents}) != len(ids):
            raise ValueError("Document IDs and URLs must be unique within a case")
        if not {self.supplied_document_id, *self.retrieval_document_ids} <= set(ids):
            raise ValueError("Every supplied/retrieval document must resolve to the frozen corpus")
        if self.labels and not {c.document_id for c in self.labels.claims} <= set(ids):
            raise ValueError("Reference labels must resolve to corpus document IDs")
        return self


class Corpus(StrictModel):
    version: Literal[1] = 1
    synthetic: bool
    provenance: str = Field(min_length=10, max_length=2000)
    cases: list[BenchmarkCase] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def unique_case_ids(self) -> "Corpus":
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Case IDs must be unique so one opt-in cannot select multiple cases")
        return self


class FrozenFetcher:
    def __init__(self, documents: dict[str, DocumentContent]):
        self.documents = documents

    def fetch(self, url: str, budget: Budget) -> DocumentContent:
        budget.check()
        if url not in self.documents:
            raise ResearchError("outside_corpus", "Source is not in the frozen experiment corpus")
        return self.documents[url]

    def close(self) -> None:
        pass


class FixedRetrievalProvider:
    """A/B share the extractor and verifier with C; only C has model-driven planning/decisions."""

    def __init__(self, provider: ModelProvider, plan: PlanSpec, urls: list[str]):
        self.provider, self.plan, self.urls = provider, plan, urls

    def generate(self, output: type[T], task: str, payload: dict[str, Any], budget: Budget) -> T:
        if output is PlanSpec:
            return output.model_validate(self.plan.model_dump())
        if output is Decision:
            pending = {c["url"]: c["id"] for c in payload["observations"]["candidates"]}
            target = next((pending[url] for url in self.urls if url in pending), None)
            return output.model_validate(
                {
                    "action": "fetch" if target else "stop",
                    "target_id": target,
                    "summary": "Fixed document schedule without adaptive planning or search",
                }
            )
        return self.provider.generate(output, task, payload, budget)


def load_documents(case: BenchmarkCase, root: Path, synthetic: bool) -> dict[str, DocumentContent]:
    result = {}
    policy = URLPolicy([urlsplit(d.url).hostname or "" for d in case.documents])
    for item in case.documents:
        path = (root / item.path).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Corpus paths must be existing files inside the manifest directory")
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Corpus documents must fit the source-tool 2 MiB limit")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item.sha256:
            raise ValueError("Corpus hash mismatch; re-annotate changed document versions")
        url = policy.validate(item.url)
        doc = normalize_document(url, raw, item.media_type)
        doc.synthetic = synthetic
        result[url] = doc
    if case.labels:
        by_id = {d.id: result[d.url] for d in case.documents}
        for claim in case.labels.claims:
            if exact_span(by_id[claim.document_id].text, claim.support_quote) is None:
                raise ValueError("Reference quote does not resolve to an unambiguous corpus span")
    return result


def claim_key(url: str, field: str, value: str, scope: dict[str, Any]) -> tuple[str, ...]:
    normalized = ClaimScope.model_validate(scope).model_dump(mode="json", exclude_none=True)
    return url, field, value, json.dumps(normalized, sort_keys=True)


def measure(
    case: BenchmarkCase, report: dict[str, Any], documents: dict[str, DocumentContent], scored: bool
) -> dict[str, Any]:
    snippets = {e["id"]: e for e in report["evidence"]}
    findings = report["findings"]

    def valid(claim: dict[str, Any]) -> bool:
        for key in ("evidence_id", "scope_evidence_id"):
            evidence = snippets.get(claim[key])
            doc = documents.get(evidence["url"]) if evidence else None
            if (
                not evidence
                or not doc
                or doc.text[evidence["start"] : evidence["end"]] != evidence["quote"]
            ):
                return False
        return claim["value"] in snippets[claim["evidence_id"]]["quote"]

    metrics: dict[str, Any] = {
        "claims_emitted": len(findings),
        "exact_span_validity": sum(valid(c) for c in findings) / len(findings)
        if findings
        else None,
        "extraction_precision": None,
        "extraction_recall": None,
        "citation_correctness": None,
        "unsupported_claim_rate": None,
        "missing_information_f1": None,
        "contradiction_precision": None,
        "contradiction_recall": None,
        "research_completeness": None,
        "task_success": None,
        "failure_analysis": [],
    }
    if not scored or not case.labels:
        metrics["failure_analysis"] = [
            "No independently reviewed reference labels; quality metrics withheld"
        ]
        return metrics
    by_id = {d.id: d.url for d in case.documents}
    expected = {
        claim_key(by_id[c.document_id], str(c.field), c.value, c.scope.model_dump())
        for c in case.labels.claims
    }
    actual = {
        claim_key(snippets[c["evidence_id"]]["url"], c["field"], c["value"], c["scope"])
        for c in findings
    }
    correct = len(actual & expected)
    metrics.update(
        {
            "correct_claims": correct,
            "reference_claims": len(expected),
            "extraction_precision": correct / len(actual) if actual else None,
            "extraction_recall": correct / len(expected) if expected else None,
            "unsupported_claim_rate": len(actual - expected) / len(actual) if actual else None,
            "research_completeness": correct / len(expected) if expected else None,
        }
    )
    # Citation correctness additionally requires the annotated support span, not just a real quote.
    reference_quotes = {
        claim_key(
            by_id[c.document_id], str(c.field), c.value, c.scope.model_dump()
        ): c.support_quote
        for c in case.labels.claims
    }
    citation_correct = sum(
        valid(c)
        and snippets[c["evidence_id"]]["quote"]
        == reference_quotes.get(
            claim_key(snippets[c["evidence_id"]]["url"], c["field"], c["value"], c["scope"])
        )
        for c in findings
    )
    metrics["citation_correctness"] = citation_correct / len(findings) if findings else None
    unknowns = {u["field"] for u in report["unanswered_questions"]}
    gold_unknowns = set(case.labels.unknown_fields)
    denominator = len(unknowns) + len(gold_unknowns)
    metrics["missing_information_f1"] = (
        2 * len(unknowns & gold_unknowns) / denominator if denominator else 1.0
    )
    conflicts = {c["field"] for c in report["conflicts"]}
    gold_conflicts = set(case.labels.conflict_fields)
    metrics["contradiction_precision"] = (
        len(conflicts & gold_conflicts) / len(conflicts) if conflicts else None
    )
    metrics["contradiction_recall"] = (
        len(conflicts & gold_conflicts) / len(gold_conflicts) if gold_conflicts else None
    )
    metrics["task_success"] = (
        actual == expected and unknowns == gold_unknowns and conflicts == gold_conflicts
    )
    metrics["failure_analysis"] = [
        {"kind": "missing_reference_claim", "document": key[0], "field": key[1]}
        for key in sorted(expected - actual)
    ] + [
        {"kind": "unsupported_or_different_claim", "document": key[0], "field": key[1]}
        for key in sorted(actual - expected)
    ]
    return metrics


def run_case(
    case: BenchmarkCase,
    documents: dict[str, DocumentContent],
    approach: str,
    provider: ModelProvider,
    config: Settings,
    synthetic: bool,
    input_price: float | None = None,
    output_price: float | None = None,
) -> dict[str, Any]:
    by_id = {d.id: d.url for d in case.documents}
    urls = (
        [by_id[case.supplied_document_id]]
        if approach != "B_fixed_retrieval"
        else [by_id[i] for i in case.retrieval_document_ids]
    )
    chosen: ModelProvider = (
        provider if approach == "C_adaptive" else FixedRetrievalProvider(provider, case.plan, urls)
    )
    request = RunInput(
        objective=case.objective,
        mode="demo" if synthetic else "live",
        allow_model_requests=not synthetic,
        seed_urls=[] if synthetic else urls,
        allowed_domains=[]
        if synthetic
        else list(dict.fromkeys(urlsplit(d.url).hostname or "" for d in case.documents)),
        limits=RunLimits(
            max_iterations=10,
            max_documents=8,
            max_model_requests=24,
            max_output_tokens=24000,
            max_seconds=180,
        ),
    )
    with tempfile.TemporaryDirectory(prefix="atlas-experiment-") as folder:
        engine = create_engine(f"sqlite:///{folder}/experiment.db")
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine, expire_on_commit=False)
        with sessions() as session:
            run = ResearchRun(
                objective=request.objective,
                mode=request.mode,
                request=request.model_dump(mode="json"),
            )
            session.add(run)
            session.commit()
            run_id = run.id
        research = ResearchEngine(sessions, run_id, chosen, FrozenFetcher(documents), config)
        # Demo network policy remains synthetic, but baseline B gets its fixed supplied documents.
        research.seeds = urls
        started = time.perf_counter()
        research.execute()
        elapsed = time.perf_counter() - started
        with sessions() as session:
            row, stored = session.get(ResearchRun, run_id), session.get(ResearchReport, run_id)
            assert row and stored
            stats = row.stats
            scored = synthetic or bool(
                case.labels and case.labels.status == "independently_reviewed"
            )
            metrics = measure(case, stored.content, documents, scored)
            raw_claims = list(
                session.scalars(select(ExtractedClaim).where(ExtractedClaim.run_id == run_id))
            )
            metrics["raw_extraction_precision"] = None
            metrics["raw_extraction_recall"] = None
            if scored and case.labels:
                doc_urls = {s["document_id"]: s["url"] for s in stored.content["sources"]}
                reference = {
                    claim_key(by_id[c.document_id], str(c.field), c.value, c.scope.model_dump())
                    for c in case.labels.claims
                }
                raw = {
                    claim_key(doc_urls[c.document_id], c.field, c.value, c.scope)
                    for c in raw_claims
                }
                metrics["raw_extraction_precision"] = (
                    len(raw & reference) / len(raw) if raw else None
                )
                metrics["raw_extraction_recall"] = (
                    len(raw & reference) / len(reference) if reference else None
                )
            calls = stats.get("model_http_requests", 0)
            complete_usage = stats.get("usage_reported_requests", 0) == calls
            cost = (
                0.0
                if not calls
                else (
                    (
                        stats.get("input_tokens_reported", 0) * input_price
                        + stats.get("output_tokens_reported", 0) * output_price
                    )
                    / 1_000_000
                    if complete_usage and input_price is not None and output_price is not None
                    else None
                )
            )
            result = {
                "case": case.id,
                "approach": approach,
                "status": row.status,
                "outcome": row.outcome,
                "stop_reason": row.stop_reason,
                "annotation_status": case.labels.status if case.labels else "unannotated",
                "quality_scores_available": scored,
                "metrics": metrics,
                "tool_calls": stats.get("tool_calls", 0),
                "provider_requests": stats.get("provider_requests", 0),
                "actual_model_requests": calls,
                "latency_seconds": round(elapsed, 4),
                "input_tokens": stats.get("input_tokens_reported") if calls else None,
                "output_tokens": stats.get("output_tokens_reported") if calls else None,
                "usage_complete": complete_usage if calls else None,
                "estimated_model_cost_usd": cost,
                "source_failures": sum(not s["document_id"] for s in stored.content["sources"]),
                "invalid_provider_responses": stats.get("invalid_provider_responses", 0),
                "partial_findings_retained": len(stored.content["findings"]),
                "unverified_candidates": stored.content["unverified_candidate_count"],
                "candidate_support_labels": [
                    {"field": c.field, "label": c.semantic_assessment.get("label", "not_assessed")}
                    for c in raw_claims
                ],
                "failure_recovery_experiment": "not injected; see regression tests",
                "plan_revisions": stored.content["run_metadata"]["plan_revisions"],
                "run_limits": request.limits.model_dump(mode="json"),
                "predictions": [
                    {
                        "field": c["field"],
                        "value": c["value"],
                        "scope": c["scope"],
                        "support": next(
                            e for e in stored.content["evidence"] if e["id"] == c["evidence_id"]
                        ),
                        "scope_support": next(
                            e
                            for e in stored.content["evidence"]
                            if e["id"] == c["scope_evidence_id"]
                        ),
                    }
                    for c in stored.content["findings"]
                ],
                "decision_trace": [
                    {"summary": step.summary, **step.data}
                    for step in session.scalars(
                        select(ResearchStep)
                        .where(ResearchStep.run_id == run_id, ResearchStep.node == "DECIDE")
                        .order_by(ResearchStep.sequence)
                    )
                ],
            }
        engine.dispose()
    return result


def synthetic_corpus() -> tuple[Corpus, Path]:
    root = Path(__file__).with_name("fixtures")
    gold = json.loads((root / "gold.json").read_text())
    plan = PlanSpec.model_validate(
        {
            "questions": [
                {
                    "id": "q1",
                    "question": "Funding, deadline and financial documentation?",
                    "fields": ["tuition_funding", "living_stipend", "deadline", "proof_of_funds"],
                    "completion_criterion": "Source evidence for each requested field",
                }
            ],
            "completion_criteria": ["Answer or mark unknown every requested field"],
        }
    )
    cases = []
    for scenario, filename in [
        ("funding_gap", "award.html"),
        ("conflict", "conflict.html"),
        ("insufficient", "insufficient.html"),
    ]:
        documents = []
        normalized = {}
        for doc_id, url, name in [
            ("program", DEMO_SEED, "program.html"),
            ("award", DEMO_AWARD, filename),
        ]:
            raw = (root / name).read_bytes()
            documents.append(
                CorpusDocument(
                    id=doc_id,
                    url=url,
                    path=name,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    media_type="text/html",
                    retrieved_at="bundled synthetic fixture; no retrieval",
                    source_owner="ATLAS synthetic fixture",
                    reuse_note="Project fixture under repository license",
                )
            )
            normalized[doc_id] = normalize_document(url, raw, "text/html").text
        claims = [
            ReferenceClaim(
                document_id=d,
                field=f,
                value=v,
                scope=ClaimScope(program="Lumen AI Master's", intake_year=2027),
                support_quote=next(
                    line for line in normalized[d].splitlines() if line.endswith(": " + v)
                ),
            )
            for d, f, v in gold[scenario]["claims"]
        ]
        # The program value also appears in its heading; gold support is the labeled Program line.
        for claim in claims:
            if claim.field == ResearchField.program:
                claim.support_quote = "Program: " + claim.value
        cases.append(
            BenchmarkCase(
                id=scenario,
                objective=DEMO_OBJECTIVE,
                documents=documents,
                supplied_document_id="program",
                retrieval_document_ids=["program", "award"],
                plan=plan,
                labels=ReferenceLabels(
                    status="author_labeled",
                    annotators=["ATLAS fixture author (synthetic controls)"],
                    claims=claims,
                    unknown_fields=gold[scenario]["unknown_fields"],
                    conflict_fields=gold[scenario]["conflict_fields"],
                    annotation_notes="Authored fixture labels; not independent human judgments.",
                ),
            )
        )
    return Corpus(
        synthetic=True,
        provenance="Tiny deterministic engineering controls, not real AI quality.",
        cases=cases,
    ), root


def semantic_controls() -> dict[str, Any]:
    dataset = json.loads(
        Path(__file__).with_name("fixtures").joinpath("semantic-cases.json").read_text()
    )
    records = []
    for case in dataset["cases"]:
        assessment = assess_support(
            case["field"],
            case["value"],
            case["quote"],
            case["text"],
            exact_span(case["text"], case["quote"]),
            case.get("scope_valid", True),
            {"program": "Synthetic MSc", "intake_year": case.get("intake_year", 2027)},
            case.get("target_year"),
        )
        records.append(
            {
                "case": case["id"],
                "expected": case["expected"],
                "actual": assessment["label"],
                "reason": assessment["reason"],
            }
        )
    return {
        "provenance": dataset["provenance"],
        "cases": records,
        "correct": sum(c["expected"] == c["actual"] for c in records),
        "total": len(records),
    }


def capture(url: str, output: Path) -> dict[str, Any]:
    """One explicit URL, bounded robots-respecting retrieval; raw snapshots stay outside Git."""
    policy = URLPolicy([urlsplit(url).hostname or ""])
    policy.validate(url)
    fetcher = SafeFetcher(policy)
    try:
        with tempfile.TemporaryDirectory(prefix="atlas-capture-") as folder:
            engine = create_engine(f"sqlite:///{folder}/capture.db")
            Base.metadata.create_all(engine)
            sessions = sessionmaker(engine)
            with sessions() as session:
                run = ResearchRun(
                    objective="Capture one approved public research document",
                    mode="capture",
                    request={},
                )
                session.add(run)
                session.commit()
                run_id = run.id
            budget = Budget(sessions, run_id, RunLimits(max_seconds=25, max_network_requests=8))
            try:
                doc = fetcher.fetch(url, budget)
                output.mkdir(parents=True, exist_ok=True)
                path = output / (
                    doc.sha256 + (".pdf" if doc.media_type == "application/pdf" else ".html")
                )
                if not path.exists():
                    path.write_bytes(doc.raw)
                result = {
                    "status": "retrieved_unannotated",
                    "url": doc.url,
                    "sha256": doc.sha256,
                    "media_type": doc.media_type,
                    "path": path.name,
                    "retrieved_at": utc_iso(utcnow()),
                    "source_owner": "Requires human confirmation",
                    "reuse_note": "Confirm reuse terms before redistributing.",
                }
            except ResearchError as exc:
                result = {
                    "status": "blocked",
                    "url": url,
                    "code": exc.code,
                    "message": exc.message,
                    "attempted_at": utc_iso(utcnow()),
                }
            engine.dispose()
            return result
    finally:
        fetcher.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--allow-model-requests", action="store_true")
    parser.add_argument("--capture-url")
    parser.add_argument("--capture-dir", type=Path, default=Path("data/corpus"))
    parser.add_argument("--case")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input-usd-per-million", type=float)
    parser.add_argument("--output-usd-per-million", type=float)
    args = parser.parse_args()
    if args.capture_url:
        result: dict[str, Any] = capture(args.capture_url, args.capture_dir)
    else:
        if args.manifest:
            corpus = Corpus.model_validate_json(args.manifest.read_text())
            root = args.manifest.parent
        else:
            corpus, root = synthetic_corpus()
        if not corpus.synthetic and not (args.allow_model_requests and args.case):
            parser.error(
                "Authentic experiments require --allow-model-requests and one explicit --case"
            )
        if any(
            p is not None and (p < 0 or p != p or p == float("inf"))
            for p in (args.input_usd_per_million, args.output_usd_per_million)
        ):
            parser.error("Prices must be finite nonnegative USD amounts")
        config = Settings()
        provider: ModelProvider = (
            DemoProvider() if corpus.synthetic else OpenAICompatibleProvider(config)
        )
        cases = [case for case in corpus.cases if not args.case or case.id == args.case]
        if not cases:
            parser.error("Case ID was not found")
        results: list[dict[str, Any]] = []
        for case in cases:
            docs = load_documents(case, root, corpus.synthetic)
            results.extend(
                run_case(
                    case,
                    docs,
                    approach,
                    provider,
                    config,
                    corpus.synthetic,
                    args.input_usd_per_million,
                    args.output_usd_per_million,
                )
                for approach in APPROACHES
            )
        result = {
            "experiment": "frozen_corpus_abc",
            "synthetic": corpus.synthetic,
            "real_model_quality_evaluated": not corpus.synthetic
            and any(r["quality_scores_available"] and r["actual_model_requests"] for r in results),
            "provenance": corpus.provenance,
            "corpus_manifest_sha256": hashlib.sha256(corpus.model_dump_json().encode()).hexdigest(),
            "source_versions": [
                {
                    "case": case.id,
                    "documents": [d.model_dump(mode="json") for d in case.documents],
                    "annotation_status": case.labels.status if case.labels else "unannotated",
                }
                for case in cases
            ],
            "software_versions": {
                name: version(name) for name in ("langgraph", "httpx", "pydantic")
            },
            "cost_basis_usd_per_million": {
                "input": args.input_usd_per_million,
                "output": args.output_usd_per_million,
            },
            "generated_at": utc_iso(utcnow()),
            "model": config.llm_model if not corpus.synthetic else "deterministic_fixture_provider",
            "settings": {
                "temperature": 0,
                "json_mode": config.llm_json_mode,
                "max_output_tokens_per_request": config.llm_max_output_tokens,
            },
            "results": results,
            "semantic_controls": semantic_controls(),
            "limitations": [
                "A/B/C share extraction/verification; A/B use fixed document schedules.",
                "Frozen replay tests research over snapshots, not live discovery/availability.",
                "Synthetic controls are authored; authentic scores need independent review.",
                "Conflict/unknown metrics compare fields, not per-applicant semantic judgments.",
                "Null means unmeasured or undefined, not zero cost or successful quality.",
                "Latency includes persistence; no statistical performance claim is made.",
            ],
        }
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    if result.get("status") == "blocked" or any(
        r["status"] != "completed" for r in result.get("results", [])
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
