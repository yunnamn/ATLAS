"""Transparent rules, never an admissions probability."""

import re
from typing import Any

from atlas.schemas import FactKey, OpportunityInput, UserProfile


def evaluate(op: OpportunityInput, profile: UserProfile) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    warnings: list[str] = []

    def requirement(key: str, candidate: object, passes: bool, detail: str) -> None:
        fact = op.facts[FactKey(key)]
        outcome = (
            "unknown" if fact.value is None or candidate is None else ("match" if passes else "gap")
        )
        if fact.state == "unverified" and outcome != "unknown":
            outcome = "provisional_match" if passes else "provisional_gap"
        checks.append({"kind": "requirement", "label": key, "outcome": outcome, "detail": detail})

    def value(key: str) -> str | None:
        return op.facts[FactKey(key)].value

    nationalities = value("eligible_nationalities")
    codes = [x.strip().upper() for x in (nationalities or "").split(",")]
    nationality_readable = nationalities is not None and (
        nationalities.casefold() == "all"
        or re.fullmatch(r"[A-Z]{2}(?:,\s*[A-Z]{2})*", nationalities) is not None
    )
    requirement(
        "eligible_nationalities",
        profile.nationality if nationality_readable else None,
        "ALL" in codes or profile.nationality in codes,
        f"Published nationality rule: {nationalities or 'not recorded'}.",
    )
    minimum = value("min_gpa")
    requirement(
        "min_gpa",
        profile.gpa,
        profile.gpa is not None and minimum is not None and profile.gpa >= float(minimum),
        f"Minimum GPA: {minimum or 'not recorded'} on a 4.0 scale.",
    )
    language = value("language")
    requirement(
        "language",
        profile.ielts,
        profile.ielts is not None and language is not None and profile.ielts >= float(language),
        f"Minimum IELTS: {language or 'not recorded'}. Other language tests are not evaluated.",
    )
    degree = value("required_degree")
    degree_candidate = profile.education
    if degree not in ("bachelor", "master") or (
        degree == "bachelor" and profile.education == "master"
    ):
        # A highest degree does not prove possession of a particular prior degree.
        degree_candidate = None
    requirement(
        "required_degree",
        degree_candidate,
        degree == profile.education,
        f"Required degree: {degree or 'not recorded'}. Only the highest completed "
        "degree is recorded; prior degrees and equivalent qualifications require manual review.",
    )

    points = 0
    available = 0
    for label, enabled, matched, weight, detail in [
        (
            "Country preference",
            bool(profile.preferred_countries),
            op.country.casefold() in [c.casefold() for c in profile.preferred_countries],
            35,
            f"Destination: {op.country}.",
        ),
        (
            "Subject interests",
            bool(profile.interests),
            bool({s.casefold() for s in op.subjects} & {s.casefold() for s in profile.interests}),
            35,
            "Exact subject tags are compared with your interests.",
        ),
        (
            "Funding constraint",
            profile.requires_full_funding,
            value("funding") == "tuition_and_stipend",
            30,
            "Tuition and a living stipend are required; other costs still need review.",
        ),
    ]:
        if not enabled:
            continue
        unknown = label == "Funding constraint" and value("funding") is None
        available += weight
        points += weight if matched else 0
        outcome = "unknown" if unknown else ("match" if matched else "gap")
        if label == "Funding constraint" and op.facts[FactKey.funding].state == "unverified":
            outcome = "provisional_match" if matched else "provisional_gap"
        checks.append(
            {
                "kind": "constraint" if label == "Funding constraint" else "preference",
                "label": label,
                "outcome": outcome,
                "detail": detail,
            }
        )
    for key, text in [
        ("proof_of_funds", "Proof of funds required"),
        ("return_obligation", "Mandatory return obligation"),
    ]:
        if value(key) == "yes":
            warnings.append(text)
        elif value(key) is None:
            warnings.append(f"{key.replace('_', ' ').capitalize()} is unknown")
    fee = value("application_fee")
    if fee is None:
        warnings.append("Application fee is unknown")
    elif fee.strip().lower() not in ("0", "none", "no", "free", "0 usd", "0 eur", "0 gbp"):
        warnings.append(f"Application fee: {fee}")
    if value("funding") != "tuition_and_stipend":
        warnings.append("Full tuition and living funding is not established")
    if op.facts[FactKey.funding].state == "unverified":
        warnings.append("Funding coverage is unverified")
    for key, label in [("travel", "Travel support"), ("insurance", "Health insurance")]:
        if value(key) is None:
            warnings.append(f"{label} is unknown")
    hard = [c for c in checks if c["kind"] == "requirement"]
    status = "needs_review" if any(c["outcome"] != "match" for c in hard) else "rules_met"
    if any(c["outcome"] == "gap" for c in hard):
        status = "requirement_gap"
    return {
        "score": round(100 * points / available) if available else None,
        "label": "Preference fit",
        "eligibility": status,
        "checks": checks,
        "warnings": warnings,
        "disclaimer": "Not an admissions probability. Only recorded rules "
        "are checked; unverified evidence and unknowns require review.",
    }
