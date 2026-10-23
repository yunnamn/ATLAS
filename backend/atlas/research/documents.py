import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from atlas.research.errors import ResearchError


@dataclass
class DocumentContent:
    url: str
    title: str
    media_type: str
    raw: bytes
    text: str
    locations: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    synthetic: bool = False

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()


def normalize_document(
    url: str, content: bytes, media_type: str, timeout: float = 12
) -> DocumentContent:
    if media_type == "application/pdf":
        if not content.startswith(b"%PDF-"):
            raise ResearchError("invalid_document", "The response is not a PDF")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "atlas.services.pdf_worker"],
                input=content,
                capture_output=True,
                timeout=min(12, timeout),
                check=True,
            )
            parsed = json.loads(result.stdout)
        except (subprocess.SubprocessError, ValueError) as exc:
            raise ResearchError(
                "invalid_document", "PDF parsing failed within the safety limits"
            ) from exc
        if not parsed["text"].strip():
            raise ResearchError("no_text", "PDF contains no extractable text; OCR is unavailable")
        return DocumentContent(
            url, "PDF source", media_type, content, parsed["text"], parsed.get("page_spans", [])
        )
    if media_type not in ("text/html", "application/xhtml+xml"):
        raise ResearchError("unsupported_type", "Only HTML and PDF research sources are supported")
    soup = BeautifulSoup(content, "html.parser")
    title = soup.title.get_text(" ", strip=True)[:200] if soup.title else "HTML source"
    links = []
    for a in soup.find_all("a", href=True, limit=100):
        href = a.get("href")
        if isinstance(href, str):
            links.append({"url": urljoin(url, href), "title": a.get_text(" ", strip=True)[:200]})
    for element in soup(["script", "style", "noscript", "template", "svg", "form"]):
        element.decompose()
    text = "\n".join(
        line for line in (" ".join(x.split()) for x in soup.get_text("\n").splitlines()) if line
    )
    if not text or len(text) > 100_000:
        raise ResearchError("invalid_document", "Normalized HTML must contain 1–100,000 characters")
    return DocumentContent(url, title, media_type, content, text, [], links)
