import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpcore
import httpx

from atlas.research.budget import Budget
from atlas.research.documents import DocumentContent, normalize_document
from atlas.research.errors import BudgetExhausted, ResearchError, RunCancelled
from atlas.research.network import PinnedTransport, URLPolicy

USER_AGENT = "ATLASResearch/0.2"
MAX_DOWNLOAD = 2 * 1024 * 1024


class SafeFetcher:
    def __init__(
        self,
        policy: URLPolicy,
        min_interval: float = 1,
        transport: httpx.BaseTransport | None = None,
    ):
        self.policy, self.min_interval = policy, min_interval
        self.client = httpx.Client(
            transport=transport or PinnedTransport(),
            trust_env=False,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
        )
        self.robots: dict[str, RobotFileParser] = {}
        self.last_request: dict[str, float] = {}

    def close(self) -> None:
        self.client.close()

    def _request(
        self, url: str, budget: Budget, limit: int = MAX_DOWNLOAD, delay: float | None = None
    ) -> tuple[int, dict[str, str], bytes]:
        current = self.policy.validate(url)
        host = urlsplit(current).hostname or ""
        interval = max(self.min_interval, delay or 0)
        wait = interval - (time.monotonic() - self.last_request.get(host, 0))
        if wait > 0:
            budget.pause(wait)
        budget.increment("network_requests", budget.limits.max_network_requests)
        self.last_request[host] = time.monotonic()
        try:
            with self.client.stream(
                "GET", current, timeout=min(10, budget.remaining())
            ) as response:
                budget.check()
                # Reject compressed responses rather than risk a decompression bomb.
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ResearchError(
                        "compressed_response", "Compressed source responses are refused"
                    )
                if int(response.headers.get("content-length", "0")) > limit:
                    raise ResearchError("download_limit", "Source exceeds the download size limit")
                chunks = bytearray()
                for chunk in response.iter_raw(chunk_size=64 * 1024):
                    budget.check()
                    chunks.extend(chunk)
                    if len(chunks) > limit:
                        raise ResearchError(
                            "download_limit", "Source exceeds the download size limit"
                        )
                return response.status_code, dict(response.headers), bytes(chunks)
        except (BudgetExhausted, RunCancelled, ResearchError):
            raise
        except (
            httpx.HTTPError,
            httpcore.NetworkError,
            httpcore.TimeoutException,
            httpcore.ProtocolError,
            OSError,
            ValueError,
        ) as exc:
            raise ResearchError("network_failed", "Source retrieval failed or timed out") from exc

    def check_robots(self, url: str, budget: Budget) -> float:
        parts = urlsplit(self.policy.validate(url))
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots:
            robot_url = origin + "/robots.txt"
            for _ in range(4):
                status, headers, content = self._request(robot_url, budget, limit=128 * 1024)
                if status in (301, 302, 303, 307, 308):
                    robot_url = self.policy.validate(
                        urljoin(robot_url, headers.get("location", ""))
                    )
                    continue
                parser = RobotFileParser()
                if status == 404:
                    parser.parse(["User-agent: *", "Disallow:"])
                elif status == 200:
                    parser.parse(content.decode("utf-8", errors="replace").splitlines())
                else:
                    raise ResearchError(
                        "robots_unavailable", "Robots policy unavailable or denied access"
                    )
                self.robots[origin] = parser
                break
            else:
                raise ResearchError("redirect_limit", "Robots redirect limit reached")
        policy = self.robots[origin]
        if not policy.can_fetch(USER_AGENT, url):
            raise ResearchError("robots_denied", "Robots policy disallows this source path")
        crawl_delay = policy.crawl_delay(USER_AGENT) or policy.crawl_delay("*") or 0
        rate = policy.request_rate(USER_AGENT) or policy.request_rate("*")
        rate_delay = rate.seconds / rate.requests if rate and rate.requests > 0 else 0
        return max(self.min_interval, float(crawl_delay), rate_delay)

    def fetch(self, url: str, budget: Budget) -> DocumentContent:
        current = self.policy.validate(url)
        for _ in range(4):
            delay = self.check_robots(current, budget)
            status, headers, content = self._request(current, budget, delay=delay)
            if status in (301, 302, 303, 307, 308):
                if not headers.get("location"):
                    raise ResearchError("invalid_redirect", "Source redirect has no destination")
                current = self.policy.validate(urljoin(current, headers["location"]))
                continue
            if status != 200:
                raise ResearchError("source_unavailable", f"Source returned HTTP {status}")
            media = headers.get("content-type", "").split(";")[0].lower().strip()
            return normalize_document(current, content, media, budget.remaining())
        raise ResearchError("redirect_limit", "Source redirect limit reached")
