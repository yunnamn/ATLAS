"""Direct, DNS-pinned source HTTP. Never inherits ambient proxy credentials."""

import ipaddress
import re
import ssl
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

import dns.exception
import dns.resolver
import httpcore
import httpx
from httpcore import SyncBackend

from atlas.research.errors import ResearchError


def domain_name(value: str) -> str:
    try:
        host = value.strip().encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ResearchError("unsafe_domain", "Invalid source domain") from exc
    if (
        len(host) > 253
        or "." not in host
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        )
    ):
        raise ResearchError("unsafe_domain", "Use exact public DNS hostnames, without wildcards")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise ResearchError("unsafe_domain", "IP literals are not accepted as source domains")


class URLPolicy:
    def __init__(self, domains: list[str]):
        self.domains = {domain_name(h) for h in domains}

    def validate(self, value: str) -> str:
        if len(value) > 2000 or re.search(r"[\x00-\x20\x7f\\]", value):
            raise ResearchError("unsafe_url", "Invalid source URL")
        try:
            parts = urlsplit(value)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise ValueError("scheme")
            if parts.username is not None or parts.password is not None:
                raise ValueError("credentials")
            decoded_path = unquote(unquote(parts.path))
            if any(part in (".", "..") for part in decoded_path.split("/")) or "\\" in decoded_path:
                raise ValueError("ambiguous path")
            if re.search(r"[\x00-\x1f\x7f]", decoded_path):
                raise ValueError("control character")
            host = domain_name(parts.hostname)
            if parts.port not in (None, 80 if parts.scheme == "http" else 443):
                raise ValueError("port")
            if any(
                re.search(r"token|key|secret|password|signature|credential", name, re.I)
                for name, _ in parse_qsl(parts.query)
            ):
                raise ValueError("sensitive query")
        except (ValueError, UnicodeError) as exc:
            raise ResearchError(
                "unsafe_url",
                "Use HTTP(S) source URLs without credentials, "
                "sensitive query parameters, or nonstandard ports",
            ) from exc
        if host not in self.domains:
            raise ResearchError(
                "outside_scope", "Source hostname is outside this run's explicit scope"
            )
        return urlunsplit((parts.scheme, host, parts.path or "/", parts.query, ""))


def resolve_public(host: str, timeout: float = 3) -> list[str]:
    addresses: list[str] = []
    resolver = dns.resolver.Resolver()
    resolver.lifetime = min(3, timeout)
    resolver.timeout = min(1, timeout)
    try:
        for kind in ("A", "AAAA"):
            try:
                answer = resolver.resolve(host, kind, search=False)
                addresses.extend(str(item) for item in answer)
            except dns.resolver.NoAnswer:
                continue
    except dns.exception.DNSException as exc:
        raise ResearchError("dns_failed", "Public DNS resolution failed") from exc
    if not addresses:
        raise ResearchError("dns_failed", "No public address found")
    unsafe_ranges = [
        ipaddress.ip_network(prefix)
        for prefix in ("2002::/16", "2001::/32", "64:ff9b::/96", "64:ff9b:1::/48")
    ]
    if any(
        not ipaddress.ip_address(address).is_global
        or any(
            ipaddress.ip_address(address) in network
            for network in unsafe_ranges
            if ipaddress.ip_address(address).version == network.version
        )
        for address in addresses
    ):
        raise ResearchError("private_destination", "Non-public source destinations are blocked")
    return addresses


class PublicNetworkBackend(SyncBackend):
    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.NetworkStream:
        # Resolution is performed at the connection boundary. The socket receives an
        # actual public IP; TLS SNI, certificate verification and Host retain the DNS name.
        addresses = resolve_public(host, min(timeout or 3, 3))
        try:
            return super().connect_tcp(addresses[0], port, timeout, local_address, socket_options)
        except (OSError, httpcore.NetworkError) as exc:
            raise ResearchError("network_failed", "The public source connection failed") from exc


class CoreStream(httpx.SyncByteStream):
    def __init__(self, stream: Any):
        self.stream = stream

    def __iter__(self) -> Iterator[bytes]:
        yield from self.stream

    def close(self) -> None:
        self.stream.close()


class PinnedTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self.pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=PublicNetworkBackend(),
            retries=0,
            max_connections=1,
            max_keepalive_connections=0,
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        # Preserve the logical origin so HTTP core validates the original TLS hostname.
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        response = self.pool.handle_request(core_request)
        return httpx.Response(
            response.status,
            headers=response.headers,
            stream=CoreStream(response.stream),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self.pool.close()
