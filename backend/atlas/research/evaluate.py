"""Reproducible fixture evaluation; never an LLM quality benchmark."""

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from atlas.config import Settings
from atlas.db import Base
from atlas.research.demo import DEMO_AWARD, DEMO_OBJECTIVE, DEMO_SEED, DemoFetcher, DemoProvider
from atlas.research.engine import ResearchEngine
from atlas.research.models import ResearchReport, ResearchRun, SourceDocument
from atlas.research.schemas import RunInput


def run_evaluation() -> dict[str, Any]:
    gold = json.loads(Path(__file__).with_name("fixtures").joinpath("gold.json").read_text())
    records = []
    with tempfile.TemporaryDirectory(prefix="atlas-evaluation-") as folder:
        engine = create_engine(f"sqlite:///{folder}/evaluation.db")
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine, expire_on_commit=False)
        for scenario in ("funding_gap", "conflict", "insufficient"):
            data = RunInput(objective=DEMO_OBJECTIVE, demo_scenario=scenario)
            with sessions() as session:
                created_run = ResearchRun(
                    objective=data.objective, mode="demo", request=data.model_dump(mode="json")
                )
                session.add(created_run)
                session.commit()
                run_id = created_run.id
            ResearchEngine(
                sessions, run_id, DemoProvider(), DemoFetcher(scenario), Settings()
            ).execute()
            with sessions() as session:
                run = session.get(ResearchRun, run_id)
                report_row = session.get(ResearchReport, run_id)
                assert run and report_row
                report = report_row.content
                snippets = {e["id"]: e for e in report["evidence"]}
                actual = {
                    (snippets[c["evidence_id"]]["url"], c["field"], c["value"])
                    for c in report["findings"]
                }
                expected = {
                    (DEMO_SEED if row[0] == "program" else DEMO_AWARD, row[1], row[2])
                    for row in gold[scenario]["claims"]
                }

                def valid_span(
                    evidence_id: str, items: dict[str, Any] = snippets, db: Session = session
                ) -> bool:
                    item = items.get(evidence_id)
                    if not item:
                        return False
                    doc = db.get(SourceDocument, item["document_id"])
                    return bool(doc and doc.text[item["start"] : item["end"]] == item["quote"])

                supported = sum(
                    valid_span(c["evidence_id"])
                    and valid_span(c["scope_evidence_id"])
                    and c["value"] in snippets[c["evidence_id"]]["quote"]
                    for c in report["findings"]
                )
                conflict_fields = {c["field"] for c in report["conflicts"]}
                expected_conflicts = set(gold[scenario]["conflict_fields"])
                records.append(
                    {
                        "scenario": scenario,
                        "status": run.status,
                        "outcome": run.outcome,
                        "expected_fields": len(expected),
                        "correct_fields": len(actual & expected),
                        "false_positive_fields": len(actual - expected),
                        "missing_fields": len(expected - actual),
                        "report_claims": len(report["findings"]),
                        "citation_supported_claims": supported,
                        "unknown_fields": sorted(
                            u["field"] for u in report["unanswered_questions"]
                        ),
                        "expected_unknowns": gold[scenario]["unknown_fields"],
                        "contradiction_true_positives": len(conflict_fields & expected_conflicts),
                        "contradiction_false_positives": len(conflict_fields - expected_conflicts),
                        "contradiction_false_negatives": len(expected_conflicts - conflict_fields),
                        "tool_calls": run.stats.get("tool_calls", 0),
                        "fixture_provider_requests": run.stats.get("provider_requests", 0),
                        "real_model_requests": run.stats.get("model_http_requests", 0),
                        "network_requests": run.stats.get("network_requests", 0),
                    }
                )
        engine.dispose()
    total = sum(r["report_claims"] for r in records)
    expected_count = sum(r["expected_fields"] for r in records)
    correct = sum(r["correct_fields"] for r in records)
    return {
        "evaluation": "ATLAS deterministic synthetic fixture evaluation",
        "real_llm_quality_evaluated": False,
        "scenarios": records,
        "aggregate": {
            "workflow_completion_rate": sum(r["status"] == "completed" for r in records)
            / len(records),
            "citation_support_rate": sum(r["citation_supported_claims"] for r in records) / total
            if total
            else None,
            "labeled_field_accuracy": correct / expected_count if expected_count else None,
            "false_positive_fields": sum(r["false_positive_fields"] for r in records),
            "contradiction_true_positives": sum(r["contradiction_true_positives"] for r in records),
            "contradiction_false_positives": sum(
                r["contradiction_false_positives"] for r in records
            ),
            "contradiction_false_negatives": sum(
                r["contradiction_false_negatives"] for r in records
            ),
            "tool_calls": sum(r["tool_calls"] for r in records),
            "real_model_requests": sum(r["real_model_requests"] for r in records),
        },
        "limitations": [
            "Three tiny labeled synthetic scenarios, with deterministic fixture extraction.",
            "Exact citation support is not semantic truth or a real-model accuracy benchmark.",
            "Live model quality and real-site connectivity were not verified.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_evaluation()
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    if not all(
        r["status"] == "completed"
        and r["correct_fields"] == r["expected_fields"]
        and not r["false_positive_fields"]
        and r["unknown_fields"] == r["expected_unknowns"]
        and r["contradiction_false_positives"] == r["contradiction_false_negatives"] == 0
        for r in result["scenarios"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
