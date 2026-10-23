"""Conservative local extraction. Source text is data, never instructions."""

import hashlib
import re
from typing import Protocol

from atlas.schemas import Fact


class ExtractionProvider(Protocol):
    """Optional adapter boundary. No remote provider is installed or enabled.

    Adapters must return candidate facts, validate them, and require human review.
    A future remote adapter must be explicitly enabled; third-party APIs may cost money.
    """

    def extract(self, text: str, source_id: str) -> dict[str, Fact]: ...


class DeterministicExtractor:
    patterns = {
        "deadline": r"Deadline:\s*(\d{4}-\d{2}-\d{2})",
        "funding": r"Funding:\s*(tuition_and_stipend|tuition_only|partial|none)",
        "min_gpa": r"Minimum GPA:\s*([0-4](?:\.\d+)?)",
        "language": r"IELTS:\s*([0-9](?:\.\d+)?)",
        "proof_of_funds": r"Proof of funds:\s*(yes|no)",
        "return_obligation": r"Return obligation:\s*(yes|no)",
    }

    def extract(self, text: str, source_id: str) -> dict[str, Fact]:
        result = {}
        for key, pattern in self.patterns.items():
            # Only a single unambiguous, exact labeled line is a candidate.
            matches = list(re.finditer(r"^" + pattern + r"\s*$", text, re.MULTILINE))
            if len(matches) == 1:
                result[key] = Fact(
                    value=matches[0].group(1),
                    state="unverified",
                    source_id=source_id,
                    excerpt=matches[0].group(0).strip(),
                )
        return result


def document_source(content: bytes, label: str, kind: str = "document") -> dict[str, object]:
    return {
        "id": "document",
        "label": label,
        "kind": kind,
        "content_sha256": hashlib.sha256(content).hexdigest(),
    }
