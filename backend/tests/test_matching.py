from atlas.schemas import Fact, FactKey, OpportunityInput, UserProfile
from atlas.services.matching import evaluate


def test_unknowns_never_pass_and_no_enabled_preferences_means_no_score(record: dict) -> None:
    op = OpportunityInput.model_validate({**record, "facts": {}})
    result = evaluate(op, UserProfile(requires_full_funding=False))
    assert result["score"] is None
    assert result["eligibility"] == "needs_review"
    assert all(c["outcome"] == "unknown" for c in result["checks"])
    assert "Application fee is unknown" in result["warnings"]


def test_verified_rule_failure_is_separate_from_preference_score(record: dict) -> None:
    op = OpportunityInput.model_validate(record)
    for field in [
        FactKey.min_gpa,
        FactKey.language,
        FactKey.required_degree,
        FactKey.eligible_nationalities,
    ]:
        op.facts[field].state = "verified"
    profile = UserProfile(
        nationality="UZ",
        education="bachelor",
        gpa=2.0,
        ielts=8,
        preferred_countries=["Sweden"],
        interests=["Artificial intelligence"],
    )
    result = evaluate(op, profile)
    assert result["score"] == 100
    assert result["eligibility"] == "requirement_gap"
    assert next(c for c in result["checks"] if c["label"] == "min_gpa")["outcome"] == "gap"
    profile.gpa = 4
    assert evaluate(op, profile)["eligibility"] == "rules_met"


def test_unverified_rule_failure_is_provisional_and_risks_are_flagged(record: dict) -> None:
    op = OpportunityInput.model_validate(record)
    op.facts[FactKey.proof_of_funds] = Fact(value="yes", state="unverified")
    op.facts[FactKey.return_obligation] = Fact(value="yes", state="unverified")
    op.facts[FactKey.application_fee] = Fact(value="100 EUR", state="unverified")
    result = evaluate(op, UserProfile(gpa=2))
    assert result["eligibility"] == "needs_review"
    assert (
        next(c for c in result["checks"] if c["label"] == "min_gpa")["outcome"] == "provisional_gap"
    )
    assert "Proof of funds required" in result["warnings"]
    assert "Mandatory return obligation" in result["warnings"]
    assert "Application fee: 100 EUR" in result["warnings"]


def test_unknown_funding_does_not_receive_points(record: dict) -> None:
    op = OpportunityInput.model_validate(record)
    op.facts[FactKey.funding] = Fact()
    result = evaluate(op, UserProfile(preferred_countries=["Sweden"]))
    assert result["score"] == 54  # 35 / (35 + 30); unknown is not a success.
    funding = next(c for c in result["checks"] if c["label"] == "Funding constraint")
    assert funding["outcome"] == "unknown"


def test_prose_rules_and_prior_degrees_are_not_guessed(record: dict) -> None:
    op = OpportunityInput.model_validate(record)
    op.facts[FactKey.eligible_nationalities] = Fact(
        value="All countries except those listed on page 2", state="unverified"
    )
    result = evaluate(op, UserProfile(nationality="UZ", education="master"))
    checks = {c["label"]: c for c in result["checks"]}
    assert checks["eligible_nationalities"]["outcome"] == "unknown"
    assert checks["required_degree"]["outcome"] == "unknown"
    assert checks["Funding constraint"]["outcome"] == "provisional_match"
    assert "Funding coverage is unverified" in result["warnings"]
    assert "Travel support is unknown" in result["warnings"]
