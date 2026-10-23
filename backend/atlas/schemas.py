from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FactKey(StrEnum):
    funding = "funding"
    tuition = "tuition"
    stipend = "stipend"
    travel = "travel"
    insurance = "insurance"
    application_fee = "application_fee"
    proof_of_funds = "proof_of_funds"
    return_obligation = "return_obligation"
    deadline = "deadline"
    language = "language"
    min_gpa = "min_gpa"
    eligible_nationalities = "eligible_nationalities"
    required_degree = "required_degree"
    application_url = "application_url"
    eligibility_conditions = "eligibility_conditions"
    language_requirements = "language_requirements"
    scholarship_obligations = "scholarship_obligations"


FACT_LABELS = {
    "funding": "Funding coverage",
    "tuition": "Tuition coverage",
    "stipend": "Living stipend",
    "travel": "Travel support",
    "insurance": "Health insurance",
    "application_fee": "Application fee",
    "proof_of_funds": "Proof of funds",
    "return_obligation": "Return obligation",
    "deadline": "Application deadline",
    "language": "Minimum IELTS score",
    "min_gpa": "Minimum GPA (4.0 scale)",
    "eligible_nationalities": "Eligible nationalities (ISO codes or all)",
    "required_degree": "Required degree",
    "application_url": "Application URL",
    "eligibility_conditions": "Eligibility conditions (source wording)",
    "language_requirements": "Language requirements (source wording)",
    "scholarship_obligations": "Scholarship obligations (source wording)",
}


class Fact(StrictModel):
    value: str | None = Field(default=None, max_length=2000)
    state: Literal["unknown", "unverified", "verified"] = "unknown"
    source_id: str | None = Field(default=None, max_length=80)
    excerpt: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.state == "unknown" and self.value is not None:
            raise ValueError("Unknown facts must have a null value")
        if self.state != "unknown" and not self.value:
            raise ValueError("Known facts need a value")
        if self.state == "verified" and (not self.source_id or not self.excerpt):
            raise ValueError("Verified facts need a source and supporting excerpt")
        if self.excerpt and not self.source_id:
            raise ValueError("Excerpts need a source")
        return self


class Source(StrictModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    label: str = Field(min_length=1, max_length=200)
    kind: Literal["demo", "official_url", "document", "manual"]
    url: HttpUrl | None = None
    retrieved_at: date | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    # This is an assertion by the importer, not automated authentication of a website.
    official_asserted: bool = False

    @model_validator(mode="after")
    def url_required(self) -> Self:
        if self.kind == "official_url" and self.url is None:
            raise ValueError("A website source needs a URL")
        return self


class OpportunityInput(StrictModel):
    external_id: str = Field(min_length=1, max_length=120, pattern=r"^[\w.-]+$")
    title: str = Field(min_length=3, max_length=200)
    institution: str = Field(min_length=2, max_length=200)
    country: str = Field(min_length=2, max_length=80)
    category: Literal["masters", "fellowship", "hackathon", "job"] = "masters"
    summary: str = Field(min_length=10, max_length=5000)
    subjects: list[str] = Field(default_factory=list, max_length=20)
    synthetic: bool = False
    sources: list[Source] = Field(default_factory=list, max_length=30)
    facts: dict[FactKey, Fact] = Field(default_factory=dict)

    @field_validator("subjects")
    @classmethod
    def subjects_valid(cls, values: list[str]) -> list[str]:
        if any(not x or len(x) > 80 for x in values):
            raise ValueError("Subjects must be between 1 and 80 characters")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def evidence_valid(self) -> Self:
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Source IDs must be unique")
        for key, fact in self.facts.items():
            if fact.source_id and fact.source_id not in ids:
                raise ValueError(f"{key}: source_id must refer to a source in this record")
            if fact.value is None:
                continue
            if key == FactKey.deadline:
                date.fromisoformat(fact.value)
            if key in (FactKey.min_gpa, FactKey.language):
                try:
                    number = Decimal(fact.value)
                except InvalidOperation as exc:
                    raise ValueError(f"{key} must be numeric") from exc
                maximum = 4 if key == FactKey.min_gpa else 9
                if not number.is_finite() or not 0 <= number <= maximum:
                    raise ValueError(f"{key} must be between 0 and {maximum}")
            if key == FactKey.funding and fact.value not in (
                "tuition_and_stipend",
                "tuition_only",
                "partial",
                "none",
            ):
                raise ValueError(
                    "Funding must be tuition_and_stipend, tuition_only, partial, or none"
                )
            if key in (FactKey.proof_of_funds, FactKey.return_obligation):
                if fact.value not in ("yes", "no"):
                    raise ValueError(f"{key} must be yes or no")
            if key == FactKey.application_url:
                from pydantic import TypeAdapter

                TypeAdapter(HttpUrl).validate_python(fact.value)
        for key in FactKey:
            self.facts.setdefault(key, Fact())
        return self


class ImportBatch(StrictModel):
    opportunities: list[OpportunityInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique(self) -> Self:
        ids = [o.external_id for o in self.opportunities]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate external_id in batch")
        return self


class FactReview(StrictModel):
    fact: Fact
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=5, max_length=2000)


class UserProfile(StrictModel):
    name: str = Field(default="Your research profile", min_length=1, max_length=100)
    nationality: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    education: Literal["bachelor", "master", "other"] | None = None
    gpa: float | None = Field(default=None, ge=0, le=4, allow_inf_nan=False)
    ielts: float | None = Field(default=None, ge=0, le=9, allow_inf_nan=False)
    interests: list[str] = Field(default_factory=list, max_length=20)
    preferred_countries: list[str] = Field(default_factory=list, max_length=30)
    requires_full_funding: bool = True

    @field_validator("interests", "preferred_countries")
    @classmethod
    def bounded_strings(cls, values: list[str]) -> list[str]:
        if any(not x.strip() or len(x) > 80 for x in values):
            raise ValueError("Entries must have 1 to 80 characters")
        return list(dict.fromkeys(x.strip() for x in values))


class ApplicationInput(StrictModel):
    status: Literal["saved", "preparing", "submitted", "accepted", "closed"] = "saved"
    notes: str = Field(default="", max_length=5000)
    missing_requirements: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("missing_requirements")
    @classmethod
    def bounded_requirements(cls, values: list[str]) -> list[str]:
        if any(not x.strip() or len(x) > 200 for x in values):
            raise ValueError("Requirements must have 1 to 200 characters")
        return values
