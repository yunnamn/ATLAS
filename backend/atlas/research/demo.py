"""Explicit offline demonstration only. This module does not perform LLM research."""

from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from atlas.research.budget import Budget
from atlas.research.documents import DocumentContent, normalize_document
from atlas.research.errors import ResearchError
from atlas.research.schemas import Decision, Extraction, PlanSpec

T = TypeVar("T", bound=BaseModel)
DEMO_SEED = "https://lumen.atlas.invalid/program"
DEMO_AWARD = "https://fund.atlas.invalid/award"
DEMO_DOMAINS = ["lumen.atlas.invalid", "fund.atlas.invalid"]
DEMO_OBJECTIVE = (
    "Investigate the synthetic Lumen AI Master's 2027 tuition and living funding, "
    "deadline, and proof-of-funds requirements. This is an offline fixture demo."
)


class DemoProvider:
    """Deterministic decisions driven by stored observations, visibly labeled as a fixture."""

    def generate(self, output: type[T], task: str, payload: dict[str, Any], budget: Budget) -> T:
        budget.model_request(1000, live=False)
        if output is PlanSpec:
            data: dict[str, Any] = {
                "questions": [
                    {
                        "id": "q1",
                        "question": "Which funding and deadline claims are supported?",
                        "fields": ["tuition_funding", "living_stipend", "deadline"],
                        "completion_criterion": "Exact excerpts from the synthetic program",
                    },
                    {
                        "id": "q2",
                        "question": "Is proof of funds required?",
                        "fields": ["proof_of_funds"],
                        "completion_criterion": "Exact financial documentation evidence",
                    },
                ],
                "constraints": ["Synthetic fixture demonstration; no external requests"],
                "search_tasks": [],
                "completion_criteria": ["Answer or mark every question unknown"],
            }
        elif output is Extraction:
            mapping = {
                "Institution": "institution",
                "Program": "program",
                "Degree": "degree",
                "Intake year": "intake_year",
                "Tuition funding": "tuition_funding",
                "Living stipend": "living_stipend",
                "Application deadline": "deadline",
                "Proof of funds": "proof_of_funds",
                "Language": "language",
                "Eligibility": "eligibility",
                "Application fee": "application_fee",
                "Scholarship obligations": "scholarship_obligations",
            }
            claims = []
            text = payload["document"]["text"]
            for line in text.splitlines():
                label, separator, value = line.partition(": ")
                if separator and label in mapping:
                    claims.append(
                        {
                            "field": mapping[label],
                            "value": value,
                            "quote": line,
                            "scope": {"program": "Lumen AI Master's", "intake_year": 2027},
                            "scope_quote": "Lumen AI Master's — 2027",
                        }
                    )
            data = {"claims": claims, "missing_fields": [], "note": "Offline labeled-field fixture"}
        elif output is Decision:
            candidates = payload["observations"]["candidates"]
            missing = payload["observations"]["missing_fields"]
            if candidates:
                target = candidates[0]
                revised = None
                if "proof_of_funds" in missing and payload["observations"]["document_count"]:
                    revised = {
                        **payload["plan"],
                        "constraints": [
                            *payload["plan"]["constraints"],
                            "Follow the new award link to investigate financial documents",
                        ],
                    }
                data = {
                    "action": "fetch",
                    "target_id": target["id"],
                    "question_id": "q2" if "proof_of_funds" in missing else "q1",
                    "summary": "Inspect the linked financial handbook because proof-of-funds "
                    "evidence is missing"
                    if payload["observations"]["document_count"]
                    else "Inspect the supplied synthetic program source first",
                    "revised_plan": revised,
                }
            else:
                data = {
                    "action": "stop",
                    "summary": "No further in-scope fixture sources remain; "
                    "report supported findings, conflicts, and unanswered questions",
                }
        else:
            raise ResearchError("demo_schema", "Unsupported offline demonstration schema")
        return output.model_validate(data)


class DemoFetcher:
    def __init__(self, scenario: str):
        self.scenario = scenario

    def fetch(self, url: str, budget: Budget) -> DocumentContent:
        budget.check()
        filename = (
            "program.html"
            if url == DEMO_SEED
            else {
                "funding_gap": "award.html",
                "conflict": "conflict.html",
                "insufficient": "insufficient.html",
            }[self.scenario]
            if url == DEMO_AWARD
            else None
        )
        if filename is None:
            raise ResearchError("demo_scope", "Offline demo cannot access external sources")
        raw = Path(__file__).with_name("fixtures").joinpath(filename).read_bytes()
        document = normalize_document(url, raw, "text/html")
        document.synthetic = True
        return document

    def close(self) -> None:
        pass
