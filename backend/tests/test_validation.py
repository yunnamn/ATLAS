from copy import deepcopy

import pytest
from pydantic import ValidationError

from atlas.schemas import Fact, OpportunityInput, UserProfile


@pytest.mark.parametrize(
    "fact",
    [
        {"state": "unknown", "value": "guessed"},
        {"state": "verified", "value": "a claim"},
        {"state": "unverified", "value": None},
        {"state": "unverified", "value": "yes", "excerpt": "Unsupported excerpt"},
    ],
)
def test_fact_invariants(fact: dict) -> None:
    with pytest.raises(ValidationError):
        Fact.model_validate(fact)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("min_gpa", "NaN"),
        ("min_gpa", "4.5"),
        ("language", "10"),
        ("deadline", "2027-02-30"),
        ("funding", "fully funded probably"),
        ("proof_of_funds", "maybe"),
        ("application_url", "javascript:alert(1)"),
    ],
)
def test_domain_validation(record: dict, key: str, value: str) -> None:
    record["facts"][key] = {"state": "unverified", "value": value}
    with pytest.raises(ValidationError):
        OpportunityInput.model_validate(record)


def test_unsupported_fact_keys_and_duplicate_sources(record: dict) -> None:
    bad = deepcopy(record)
    bad["facts"]["fabricated_requirement"] = {"state": "unknown"}
    with pytest.raises(ValidationError):
        OpportunityInput.model_validate(bad)
    record["sources"] *= 2
    with pytest.raises(ValidationError):
        OpportunityInput.model_validate(record)


def test_profile_bounds() -> None:
    for data in [{"gpa": 4.1}, {"ielts": 10}, {"nationality": "Uzbekistan"}, {"gpa": float("nan")}]:
        with pytest.raises(ValidationError):
            UserProfile.model_validate(data)
