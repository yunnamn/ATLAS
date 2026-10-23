from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from atlas.schemas import StrictModel


class ResearchField(StrEnum):
    institution = "institution"
    program = "program"
    degree = "degree"
    intake_year = "intake_year"
    deadline = "deadline"
    tuition_funding = "tuition_funding"
    living_stipend = "living_stipend"
    eligibility = "eligibility"
    language = "language"
    application_fee = "application_fee"
    proof_of_funds = "proof_of_funds"
    scholarship_obligations = "scholarship_obligations"


class RunLimits(StrictModel):
    max_iterations: int = Field(default=6, ge=1, le=12)
    max_documents: int = Field(default=4, ge=1, le=8)
    max_tool_calls: int = Field(default=10, ge=1, le=20)
    max_network_requests: int = Field(default=24, ge=1, le=40)
    max_model_requests: int = Field(default=12, ge=1, le=24)
    max_output_tokens: int = Field(default=12000, ge=512, le=24000)
    max_seconds: int = Field(default=120, ge=1, le=180)


class RunInput(StrictModel):
    objective: str = Field(min_length=20, max_length=4000)
    mode: Literal["demo", "live"] = "demo"
    seed_urls: list[str] = Field(default_factory=list, max_length=8)
    allowed_domains: list[str] = Field(default_factory=list, max_length=8)
    # Optional human assertions of independent authorities, never supplied by the model.
    source_groups: dict[str, str] = Field(default_factory=dict, max_length=8)
    limits: RunLimits = Field(default_factory=RunLimits)
    allow_model_requests: bool = False
    demo_scenario: Literal["funding_gap", "conflict", "insufficient"] = "funding_gap"

    @field_validator("seed_urls")
    @classmethod
    def bounded_urls(cls, values: list[str]) -> list[str]:
        if any(len(v) > 2000 for v in values):
            raise ValueError("URLs must have at most 2000 characters")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def demo_no_external_sources(self) -> "RunInput":
        if self.mode == "demo" and (self.seed_urls or self.allowed_domains or self.source_groups):
            raise ValueError(
                "Offline demo uses bundled synthetic sources only; remove live sources"
            )
        if self.mode == "live" and not self.allow_model_requests:
            raise ValueError(
                "Live mode requires explicit consent to model requests and possible costs"
            )
        return self


class ResearchQuestion(StrictModel):
    id: str = Field(pattern=r"^q[1-9][0-9]?$", max_length=3)
    question: str = Field(min_length=5, max_length=500)
    fields: list[ResearchField] = Field(min_length=1, max_length=12)
    completion_criterion: str = Field(min_length=5, max_length=500)


class PlanSpec(StrictModel):
    questions: list[ResearchQuestion] = Field(min_length=1, max_length=8)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    search_tasks: list[str] = Field(default_factory=list, max_length=8)
    completion_criteria: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def bounded_unique(self) -> "PlanSpec":
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Research question IDs must be unique")
        if any(
            len(x) > 500 for x in self.constraints + self.search_tasks + self.completion_criteria
        ):
            raise ValueError("Plan items must have at most 500 characters")
        return self


class Decision(StrictModel):
    action: Literal["fetch", "search", "reextract", "stop"]
    target_id: str | None = Field(default=None, max_length=80)
    question_id: str | None = Field(default=None, max_length=3)
    query: str | None = Field(default=None, max_length=300)
    summary: str = Field(
        min_length=5,
        max_length=500,
        description="Brief observable action summary, never private reasoning",
    )
    revised_plan: PlanSpec | None = None
    window_start: int = Field(default=0, ge=0, le=100000)


class ClaimScope(StrictModel):
    program: str = Field(min_length=2, max_length=200)
    intake_year: int | None = Field(default=None, ge=2020, le=2100)


class ClaimCandidate(StrictModel):
    field: ResearchField
    value: str = Field(
        min_length=1,
        max_length=1000,
        description="Exact value phrase from the supporting quotation",
    )
    quote: str = Field(min_length=3, max_length=3000)
    scope: ClaimScope
    scope_quote: str = Field(
        min_length=3,
        max_length=1500,
        description="Exact source text establishing program and intake year",
    )
    start: int | None = Field(default=None, ge=0)


class Extraction(StrictModel):
    claims: list[ClaimCandidate] = Field(default_factory=list, max_length=30)
    missing_fields: list[ResearchField] = Field(default_factory=list, max_length=12)
    note: str = Field(default="", max_length=500)


class AgentState(StrictModel):
    run_id: str
    action: Literal["fetch", "search", "reextract", "stop", "invalid"] = "stop"
    target_id: str | None = None
    question_id: str | None = None
    query: str | None = None
    summary: str = ""
    document_id: str | None = None
    phase: str = "PLAN"
    window_start: int = Field(default=0, ge=0, le=100000)
