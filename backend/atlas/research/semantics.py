"""Conservative English support screening, never an independent truth oracle.

Exact citations and field predicates are necessary but cannot establish general entailment.
Every decision keeps its inspected context and a concrete route to resolve uncertainty.
"""

import re
from typing import Any

PREDICATES = {
    "institution": r"institution|university|institute|college",
    "program": r"program|master|msc|degree",
    "degree": r"degree|master|msc|bachelor|phd",
    "intake_year": r"intake|cohort|entry|admission",
    "deadline": r"deadline|closing|apply by|applications? (?:close|due)",
    "tuition_funding": r"tuition|fee waiver",
    "living_stipend": r"stipend|living|maintenance|monthly allowance",
    "eligibility": r"eligib|applicant|bachelor|citizen|nationalit",
    "language": r"language|english|ielts|toefl|cefr",
    "application_fee": r"application fee|processing fee|apply free",
    "proof_of_funds": r"proof of funds|bank statement|financial (?:proof|documentation)",
    "scholarship_obligations": r"obligation|return|repay|mandatory|must|service commitment",
}
QUALIFIERS = r"\b(?:only|except|unless|may|might|conditional|subject to|provided that|up to)\b"
NEGATION = r"\b(?:no|not|never|without)\b"


def requested_year(objective: str, explicit: int | None = None) -> int | None:
    years = set(re.findall(r"\b20[2-9][0-9]\b", objective))
    return explicit or (int(next(iter(years))) if len(years) == 1 else None)


def context_scope_valid(text: str, support: tuple[int, int] | None, scope: dict[str, Any]) -> bool:
    """Reject known cross-program/intake quotation splicing in labeled English documents.

    This does not recover arbitrary document structure; absence of a marker proves nothing.
    """
    if not support:
        return False
    program = scope["program"].casefold()
    for line in reversed(text[: support[0]].splitlines()):
        declaration = line.startswith("Program:")
        dated_heading = bool(re.search(r"(?:master|msc|m\.sc\.).*\b20\d{2}\b", line, re.I))
        if not declaration and not dated_heading:
            continue
        if program not in line.casefold():
            return False
        years = re.findall(r"\b20\d{2}\b", line)
        if years and scope.get("intake_year") and str(scope["intake_year"]) not in years:
            return False
        if dated_heading:
            break
    return True


def assess_support(
    field: str,
    value: str,
    quote: str,
    text: str,
    span: tuple[int, int] | None,
    scope_valid: bool,
    scope: dict[str, Any],
    target_year: int | None = None,
) -> dict[str, Any]:
    def result(label: str, reason: str, resolution: str, passage: str = "") -> dict[str, Any]:
        return {
            "label": label,
            "method": "conservative_rules_v1",
            "independent_ground_truth": False,
            "reason": reason,
            "resolution": resolution,
            "passage": passage[:4000],
            "span": list(span) if span else None,
            "limitations": "English lexical/context screening; human semantic review is required.",
        }

    if not span or value not in quote:
        return result(
            "unsupported",
            "invalid_citation_or_value",
            "Supply an unambiguous exact supporting passage containing the proposed value.",
        )
    # Inspect the entire source line, including context omitted from a short quote.
    start = text.rfind("\n", 0, span[0]) + 1
    end = text.find("\n", span[1])
    end = len(text) if end < 0 else end
    passage = text[start:end]
    if len(passage) > 4000:
        return result(
            "insufficient_evidence",
            "context_exceeds_review_window",
            "Inspect the complete paragraph and narrow the evidence without dropping conditions.",
            passage,
        )
    following = text[end + 1 :].split("\n", 1)[0]
    preceding = text[: max(0, start - 1)].rsplit("\n", 1)[-1]
    for adjacent in (preceding, following):
        if re.match(
            r"(?:only|except|unless|subject to|provided that|conditional)\b", adjacent, re.I
        ):
            passage += "\n" + adjacent[:1000]
    if not scope_valid:
        return result(
            "insufficient_evidence",
            "scope_not_established",
            "Find an exact passage establishing program, intake and applicant/award scope.",
            passage,
        )
    if target_year and scope.get("intake_year") != target_year:
        return result(
            "insufficient_evidence",
            "outdated_or_other_intake",
            f"Obtain official evidence explicitly applicable to the {target_year} intake.",
            passage,
        )
    if re.search(
        r"ignore (?:all |previous )?instructions|system prompt|assistant:|reveal.*secret",
        passage,
        re.I,
    ):
        return result(
            "insufficient_evidence",
            "source_instruction_not_factual_evidence",
            "Locate a factual program statement outside instruction-like material.",
            passage,
        )
    # Bind the field predicate to the sentence containing the value, not a nearby unrelated fee.
    clauses = re.split(r"[;.!?](?:\s+|$)", passage)
    matching_clauses = [clause for clause in clauses if value in clause]
    assertion = " ".join(matching_clauses) if matching_clauses else passage
    predicate = PREDICATES.get(field)
    if not predicate or not re.search(predicate, assertion, re.I):
        return result(
            "unsupported",
            "wrong_or_unestablished_predicate",
            "Find a passage stating this field rather than another financial/academic condition.",
            passage,
        )
    restrictions = re.findall(
        r"\b(?:domestic|international|non-eu|eu|doctoral|self-funded) applicants\b",
        passage + "\n" + preceding,
        re.I,
    )
    if any(
        restriction.casefold() not in value.casefold()
        and restriction.casefold() != str(scope.get("applicant_group", "")).casefold()
        for restriction in restrictions
    ):
        return result(
            "partially_supported",
            "applicant_restriction_not_retained",
            "Retain the explicit applicant restriction in the value and scope.",
            passage,
        )
    missing_negations = set(re.findall(NEGATION, passage.casefold())) - set(
        re.findall(NEGATION, value.casefold())
    )
    if missing_negations:
        return result(
            "contradicted",
            "omitted_negation",
            "Retain the source negation and review whether the claim reverses its meaning.",
            passage,
        )
    missing_conditions = set(re.findall(QUALIFIERS, passage.casefold())) - set(
        re.findall(QUALIFIERS, value.casefold())
    )
    if missing_conditions:
        return result(
            "partially_supported",
            "omitted_condition",
            "Include the complete condition, limit, exception or applicant restriction.",
            passage,
        )
    return result(
        "fully_supported",
        "bounded_context_checks_passed",
        "Human review must still check meaning, source authority, currency and completeness.",
        passage,
    )


def scope_relation(
    left: dict[str, Any], right: dict[str, Any], *, same_url_version_change: bool = False
) -> str:
    for key, label in (
        ("program", "different_program"),
        ("intake_year", "different_intake"),
        ("award_track", "different_award_track"),
        ("applicant_group", "different_applicant_group"),
    ):
        a, b = left.get(key), right.get(key)
        if a != b:
            return label if a is not None and b is not None else "incomplete_scope"
    if not left.get("intake_year"):
        return "incomplete_scope"
    if same_url_version_change:
        return "different_source_version"
    a, b = left.get("source_version"), right.get("source_version")
    if a != b:
        return "different_source_version" if a is not None and b is not None else "incomplete_scope"
    return "same_scope"
