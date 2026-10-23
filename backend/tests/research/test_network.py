from unittest.mock import patch

import dns.resolver
import httpx
import pytest
from httpcore import SyncBackend

from atlas.research.budget import Budget
from atlas.research.documents import normalize_document
from atlas.research.errors import BudgetExhausted, ResearchError
from atlas.research.fetcher import SafeFetcher
from atlas.research.network import PublicNetworkBackend, URLPolicy, resolve_public
from atlas.research.schemas import RunLimits
from tests.research.helpers import make_run
from tests.test_extraction import pdf_bytes


def response(status, *, text="", content=None, headers=None):
    body = content if content is not None else text.encode()
    return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body))


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.edu/file",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://169.254.169.254/latest",
        "https://user:pass@example.edu/",
        "https://example.edu:8443/",
        "https://other.edu/program",
        "https://example.edu.evil.com/",
        "https://example.edu/p?access_token=secret",
        "https://example.edu/../private",
        "https://example.edu/%2e%2e/private",
        "https://example.edu/%00",
        "https://example.edu/\\@127.0.0.1",
        "https://example.edu.//program",
    ],
)
def test_url_policy_blocks_unsafe_or_unscoped_destinations(url) -> None:
    with pytest.raises(ResearchError):
        URLPolicy(["example.edu"]).validate(url)


def test_valid_url_is_canonical_and_fragment_does_not_change_document_identity() -> None:
    assert (
        URLPolicy(["example.edu"]).validate("https://EXAMPLE.edu/program#funding")
        == "https://example.edu/program"
    )


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["169.254.169.254"],
        ["::1"],
        ["fe80::1"],
        ["93.184.216.34", "192.168.1.1"],
        ["::ffff:127.0.0.1"],
        ["2002:7f00:1::"],
        ["64:ff9b::7f00:1"],
    ],
)
def test_dns_rebinding_and_private_mixed_answers_fail_closed(monkeypatch, addresses) -> None:
    monkeypatch.setattr(dns.resolver.Resolver, "resolve", lambda *args, **kwargs: addresses)
    with pytest.raises(ResearchError, match="Non-public"):
        resolve_public("example.edu")


def test_connector_uses_a_validated_ip_instead_of_resolving_host_again(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.research.network.resolve_public", lambda host, timeout: ["93.184.216.34"]
    )
    sentinel = object()
    with patch.object(SyncBackend, "connect_tcp", return_value=sentinel) as connect:
        assert PublicNetworkBackend().connect_tcp("example.edu", 443, 2) is sentinel
        assert connect.call_args.args[:2] == ("93.184.216.34", 443)


def budget(sessions, **limits) -> Budget:
    model = RunLimits(**limits)
    return Budget(sessions, make_run(sessions, limits=model), model)


def test_html_fetch_respects_robots_and_strips_scripts(sessions) -> None:
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return response(200, text="User-agent: *\nDisallow: /private")
        return response(
            200,
            headers={"Content-Type": "text/html"},
            text="<html><title>Program</title><script>steal()</script>"
            '<p>Tuition funding: full tuition</p><a href="/funding">Funding</a></html>',
        )

    fetcher = SafeFetcher(
        URLPolicy(["example.edu"]), min_interval=0, transport=httpx.MockTransport(handler)
    )
    doc = fetcher.fetch("https://example.edu/program", budget(sessions))
    assert "steal" not in doc.text and "full tuition" in doc.text
    assert doc.links[0]["url"] == "https://example.edu/funding"
    with pytest.raises(ResearchError, match="disallows"):
        fetcher.fetch("https://example.edu/private", budget(sessions))
    assert "https://example.edu/private" not in requests
    fetcher.close()


@pytest.mark.parametrize("target", ["http://169.254.169.254/latest", "https://other.edu/program"])
def test_redirects_are_validated_before_any_second_destination_request(sessions, target) -> None:
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return (
            response(404)
            if request.url.path == "/robots.txt"
            else response(302, headers={"Location": target})
        )

    with pytest.raises(ResearchError):
        SafeFetcher(URLPolicy(["example.edu"]), 0, httpx.MockTransport(handler)).fetch(
            "https://example.edu/program", budget(sessions)
        )
    assert len(requests) == 2 and all("example.edu" in u for u in requests)


def test_redirect_target_robots_are_checked_on_every_host(sessions) -> None:
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if request.url.host == "example.edu":
            return (
                response(404)
                if request.url.path == "/robots.txt"
                else response(302, headers={"Location": "https://funder.org/award"})
            )
        assert request.url.path == "/robots.txt"
        return response(200, text="User-agent: *\nDisallow: /")

    with pytest.raises(ResearchError, match="disallows"):
        SafeFetcher(
            URLPolicy(["example.edu", "funder.org"]), 0, httpx.MockTransport(handler)
        ).fetch("https://example.edu/program", budget(sessions))
    assert requests[-1] == "https://funder.org/robots.txt"


@pytest.mark.parametrize(
    ("headers", "body", "code"),
    [
        ({"content-type": "text/html", "content-length": "999999999"}, b"small", "download_limit"),
        ({"content-type": "text/html", "content-encoding": "gzip"}, b"x", "compressed_response"),
        ({"content-type": "application/zip"}, b"PK", "unsupported_type"),
    ],
)
def test_document_limits_fail_closed(sessions, headers, body, code) -> None:
    def handler(request):
        return (
            response(404)
            if request.url.path == "/robots.txt"
            else response(200, headers=headers, content=body)
        )

    with pytest.raises(ResearchError) as error:
        SafeFetcher(URLPolicy(["example.edu"]), 0, httpx.MockTransport(handler)).fetch(
            "https://example.edu/program", budget(sessions)
        )
    assert error.value.code == code


def test_network_request_budget_counts_robots_and_redirects(sessions) -> None:
    transport = httpx.MockTransport(
        lambda req: (
            response(404)
            if req.url.path == "/robots.txt"
            else response(302, headers={"Location": "/another"})
        )
    )
    with pytest.raises(BudgetExhausted):
        SafeFetcher(URLPolicy(["example.edu"]), 0, transport).fetch(
            "https://example.edu/program", budget(sessions, max_network_requests=2)
        )


def test_pdf_normalization_includes_exact_page_offsets() -> None:
    doc = normalize_document(
        "https://example.edu/source.pdf", pdf_bytes("Deadline: 2027-05-01"), "application/pdf"
    )
    assert "2027-05-01" in doc.text
    assert doc.locations[0]["page"] == 1
    span = doc.locations[0]
    assert doc.text[span["start"] : span["end"]] == doc.text
    assert len(doc.sha256) == 64
