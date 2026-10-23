"""One bounded in-process worker. Durable artifacts, intentionally no crash resumption."""

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from atlas.config import Settings
from atlas.db import utcnow
from atlas.research.demo import DemoFetcher, DemoProvider
from atlas.research.engine import ResearchEngine
from atlas.research.errors import ResearchError
from atlas.research.fetcher import SafeFetcher
from atlas.research.models import ResearchReport, ResearchRun
from atlas.research.network import URLPolicy, domain_name
from atlas.research.providers import OpenAICompatibleProvider, SearxNGSearch, trusted_endpoint
from atlas.research.reporting import build_report
from atlas.research.schemas import RunInput


def prepare_request(data: RunInput, settings: Settings) -> RunInput:
    if data.mode == "demo":
        return data
    OpenAICompatibleProvider(settings)  # Validate configuration, without sending a request.
    domains = [domain_name(d) for d in data.allowed_domains]
    for url in data.seed_urls:
        try:
            host = urlsplit(url).hostname
        except ValueError as exc:
            raise ResearchError("unsafe_url", "Invalid starting source URL") from exc
        if not host:
            raise ResearchError("unsafe_url", "A starting URL needs an HTTP(S) hostname")
        domains.append(domain_name(host))
    domains = list(dict.fromkeys(domains))
    if not domains or len(domains) > 8:
        raise ResearchError(
            "source_scope",
            "Live research needs 1–8 explicit source domains, including starting URL hosts",
        )
    policy = URLPolicy(domains)
    seeds = [policy.validate(url) for url in data.seed_urls]
    groups = {}
    for host, group in data.source_groups.items():
        host = domain_name(host)
        if host not in domains or not group.strip() or len(group) > 80:
            raise ResearchError(
                "source_group",
                "Source groups must identify in-scope domains "
                "using 1–80 character authority labels",
            )
        groups[host] = group.strip()
    if settings.search_base_url:
        trusted_endpoint(settings.search_base_url)
    return data.model_copy(
        update={"allowed_domains": domains, "seed_urls": seeds, "source_groups": groups}
    )


class ResearchManager:
    def __init__(self, engine: Engine, settings: Settings):
        self.sessions = sessionmaker(engine, expire_on_commit=False)
        self.settings = settings
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="atlas-research")
        self.futures: dict[str, Future[None]] = {}
        self.lock = threading.Lock()
        self.closed = False

    def start(self) -> None:
        # Replaying a node could duplicate external model costs; never do so implicitly.
        with self.sessions() as session:
            interrupted = list(
                session.scalars(
                    select(ResearchRun).where(ResearchRun.status.in_(["pending", "running"]))
                )
            )
            for run in interrupted:
                run.status, run.outcome = "failed", "partial"
                run.stop_reason, run.error = (
                    "interrupted",
                    "Worker process interrupted; start a new run",
                )
                run.finished_at = run.updated_at = utcnow()
                if not session.get(ResearchReport, run.id):
                    session.add(
                        ResearchReport(
                            run_id=run.id, content=build_report(session, run, "interrupted")
                        )
                    )
            session.commit()

    def submit(self, data: RunInput) -> str:
        data = prepare_request(data, self.settings)
        with self.lock:
            self.futures = {key: value for key, value in self.futures.items() if not value.done()}
            if self.closed or len(self.futures) >= 4:
                raise ResearchError(
                    "worker_busy", "Local research queue is full; try after a run finishes"
                )
            with self.sessions() as session:
                run = ResearchRun(
                    objective=data.objective, mode=data.mode, request=data.model_dump(mode="json")
                )
                session.add(run)
                session.commit()
                run_id = run.id
            self.futures[run_id] = self.executor.submit(self._execute, run_id)
            return run_id

    def _execute(self, run_id: str) -> None:
        with self.sessions() as session:
            run = session.get(ResearchRun, run_id)
            if not run or run.status != "pending":
                return
            data = RunInput.model_validate(run.request)
        try:
            provider = (
                DemoProvider() if data.mode == "demo" else OpenAICompatibleProvider(self.settings)
            )
            fetcher = (
                DemoFetcher(data.demo_scenario)
                if data.mode == "demo"
                else SafeFetcher(
                    URLPolicy(data.allowed_domains), self.settings.research_min_interval
                )
            )
            search = (
                SearxNGSearch(
                    self.settings.search_base_url,
                    self.settings.search_api_key.get_secret_value()
                    if self.settings.search_api_key
                    else None,
                )
                if (data.mode == "live" and self.settings.search_base_url)
                else None
            )
            ResearchEngine(
                self.sessions, run_id, provider, fetcher, self.settings, search
            ).execute()
        except Exception:
            with self.sessions() as session:
                run = session.get(ResearchRun, run_id)
                assert run
                run.status, run.outcome, run.stop_reason = (
                    "failed",
                    "partial",
                    "initialization_failed",
                )
                run.error, run.finished_at = "Could not initialize the research worker", utcnow()
                report = session.get(ResearchReport, run_id)
                if not report:
                    session.add(
                        ResearchReport(
                            run_id=run_id,
                            content=build_report(session, run, "initialization_failed"),
                        )
                    )
                session.commit()

    def cancel(self, run_id: str) -> None:
        with self.sessions() as session:
            run = session.get(ResearchRun, run_id)
            if not run:
                raise ResearchError("not_found", "Research run not found")
            if run.status not in ("pending", "running"):
                return
            run.cancel_requested = True
            run.updated_at = utcnow()
            if run.status == "pending":
                run.status, run.outcome, run.stop_reason = "cancelled", "partial", "cancelled"
                run.finished_at = utcnow()
                session.add(
                    ResearchReport(run_id=run_id, content=build_report(session, run, "cancelled"))
                )
            session.commit()

    def close(self) -> None:
        with self.lock:
            self.closed = True
            for run_id, future in self.futures.items():
                if not future.done():
                    self.cancel(run_id)
        self.executor.shutdown(wait=True, cancel_futures=True)


def capabilities(settings: Settings) -> dict[str, Any]:
    live_ready = False
    try:
        OpenAICompatibleProvider(settings)
        live_ready = True
    except ResearchError:
        pass
    return {
        "live_ready": live_ready,
        "model": settings.llm_model if live_ready else None,
        "search_configured": bool(settings.search_base_url),
        "offline_demo_available": True,
        "execution": "single local worker; no automatic crash resumption",
        "demo_notice": "Deterministic synthetic fixtures; no actual LLM or web research",
        "model_notice": "Live mode sends objective/source excerpts to the configured provider. "
        "Third-party APIs may have separate costs. Explicit enablement and consent are required.",
    }
