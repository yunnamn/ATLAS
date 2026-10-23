"""Isolated, time/memory-bounded PDF parser; Linux local development only."""

import io
import json
import resource
import sys

from pypdf import PdfReader


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    data = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024 or not data.startswith(b"%PDF-"):
        raise ValueError("Invalid or oversized PDF")
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted or len(reader.pages) > 30:
        raise ValueError("Use an unencrypted PDF of at most 30 pages")
    parts: list[str] = []
    spans = []
    for index, page in enumerate(reader.pages):
        start = sum(map(len, parts)) + len(parts)
        text = (page.extract_text() or "")[:100_000]
        parts.append(text)
        spans.append({"page": index + 1, "start": start, "end": start + len(text)})
        if sum(map(len, parts)) > 100_000:
            raise ValueError("Extracted document is too large")
    print(json.dumps({"text": "\n".join(parts), "pages": len(reader.pages), "page_spans": spans}))


if __name__ == "__main__":
    main()
