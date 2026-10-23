"""One conditional LangGraph; model choices operate on a bounded, persisted tool ledger."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from atlas.config import Settings
from atlas.db import utcnow
from atlas.research.budget import Budget
from atlas.research.demo import DEMO_DOMAINS, DEMO_SEED
from atlas.research.documents import DocumentContent
from atlas.research.errors import BudgetExhausted, ResearchError, RunCancelled
from atlas.research.intelligence import pack_observations, prioritize
from atlas.research.models import (
    ExtractedClaim,
    ResearchCandidate,
    ResearchPlan,
    ResearchReport,
    ResearchRun,
    ResearchStep,
    RunSource,
    SourceDocument,
)
from atlas.research.network import URLPolicy
from atlas.research.providers import ModelProvider, SearchProvider
from atlas.research.reporting import build_report, ledger, required_fields
from atlas.research.schemas import AgentState, Decision, Extraction, PlanSpec, RunInput
from atlas.research.verification import verify_claims


class FetchTool(Protocol):
    def fetch(self, url: str, budget: Budget) -> DocumentContent: ...
    def close(self) -> None: ...


class WorkflowState(TypedDict, total=False):
    run_id: str
    action: str
    target_id: str | None
    question_id: str | None
    query: str | None
    summary: str
    document_id: str | None
    phase: str
    window_start: int


class ResearchEngine:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        run_id: str,
        provider: ModelProvider,
        fetcher: FetchTool,
        settings: Settings,
        search: SearchProvider | None = None,
    ):
        self.sessions, self.run_id, self.provider = sessions, run_id, provider
        self.fetcher, self.settings, self.search = fetcher, settings, search
        with sessions() as session:
            run = session.get(ResearchRun, run_id)
            assert run is not None
            self.request = RunInput.model_validate(run.request)
        self.domains = DEMO_DOMAINS if self.request.mode == "demo" else self.request.allowed_domains
        self.seeds = [DEMO_SEED] if self.request.mode == "demo" else self.request.seed_urls
        self.policy = URLPolicy(self.domains)
        self.budget = Budget(sessions, run_id, self.request.limits)

    def run_row(self, session: Session) -> ResearchRun:
        run = session.get(ResearchRun, self.run_id)
        assert run is not None
        return run

    def event(
        self,
        session: Session,
        node: str,
        summary: str,
        state: Mapping[str, Any],
        data: dict[str, Any] | None = None,
    ) -> None:
        checkpoint = AgentState.model_validate(
            {**state, "run_id": self.run_id, "phase": node}
        ).model_dump(mode="json")
        sequence = (
            session.scalar(
                select(func.max(ResearchStep.sequence)).where(ResearchStep.run_id == self.run_id)
            )
            or 0
        ) + 1
        session.add(
            ResearchStep(
                run_id=self.run_id,
                sequence=sequence,
                node=node,
                summary=summary[:1000],
                data=data or {},
                checkpoint=checkpoint,
            )
        )
        run = self.run_row(session)
        run.state, run.updated_at = checkpoint, utcnow()
        session.commit()

    def add_candidates(
        self,
        session: Session,
        links: list[dict[str, str]],
        origin: str,
        document_id: str | None = None,
    ) -> int:
        added = 0
        total = (
            session.scalar(
                select(func.count())
                .select_from(ResearchCandidate)
                .where(ResearchCandidate.run_id == self.run_id)
            )
            or 0
        )
        for item in links:
            if total + added >= 40:
                break
            try:
                url = self.policy.validate(item["url"])
            except ResearchError:
                continue
            if session.scalar(
                select(ResearchCandidate).where(
                    ResearchCandidate.run_id == self.run_id, ResearchCandidate.url == url
                )
            ):
                continue
            session.add(
                ResearchCandidate(
                    run_id=self.run_id,
                    url=url,
                    title=item["title"][:200],
                    origin=origin,
                    discovered_from=document_id,
                )
            )
            session.flush()
            added += 1
        return added

    def plan(self, state: WorkflowState) -> dict[str, Any]:
        self.budget.check()
        plan = self.provider.generate(
            PlanSpec,
            "PLAN",
            {
                "objective": self.request.objective,
                "seed_urls": self.seeds,
                "allowed_domains": self.domains,
                "search_available": self.search is not None,
                "limits": self.request.limits.model_dump(),
            },
            self.budget,
        )
        with self.sessions() as session:
            session.add(
                ResearchPlan(run_id=self.run_id, revision=1, content=plan.model_dump(mode="json"))
            )
            self.event(
                session,
                "PLAN",
                "Created a typed research plan"
                if self.request.mode == "live"
                else "Created the explicitly synthetic offline fixture plan",
                state,
                {"plan_revision": 1},
            )
        return {"phase": "PLAN"}

    def discover(self, state: WorkflowState) -> dict[str, Any]:
        self.budget.check()
        if state.get("action") == "search":
            assert self.search is not None and state.get("query")
            self.budget.increment("tool_calls", self.request.limits.max_tool_calls)
            try:
                links = self.search.search(state["query"] or "", self.budget)
                message = "Filtered configured search results through explicit source scope"
            except (BudgetExhausted, RunCancelled):
                raise
            except ResearchError as exc:
                links, message = [], exc.message
        else:
            links = [{"url": url, "title": "User-supplied starting source"} for url in self.seeds]
            message = "Registered starting sources; broader search is " + (
                "configured" if self.search else "not configured"
            )
        with self.sessions() as session:
            count = self.add_candidates(
                session, links, "search" if state.get("action") == "search" else "seed"
            )
            self.event(
                session,
                "DISCOVER",
                message,
                state,
                {
                    "added_candidates": count,
                    "query": state.get("query") if state.get("action") == "search" else None,
                },
            )
        return {"phase": "DISCOVER", "action": "stop"}

    def observations(self, session: Session) -> dict[str, Any]:
        run = self.run_row(session)
        data = ledger(session, run)
        candidates = list(
            session.scalars(
                select(ResearchCandidate)
                .where(
                    ResearchCandidate.run_id == self.run_id, ResearchCandidate.status == "pending"
                )
                .order_by(ResearchCandidate.id)
            )
        )
        can_fetch = int(run.stats.get("documents_examined", 0)) < self.request.limits.max_documents
        steps = list(
            session.scalars(select(ResearchStep).where(ResearchStep.run_id == self.run_id))
        )
        extraction_counts = {
            d.id: sum(s.node == "EXTRACT" and s.data.get("document_id") == d.id for s in steps)
            for d in data["documents"].values()
        }
        documents = [
            {
                "id": d.id,
                "url": d.url,
                "title": d.title,
                "character_count": len(d.text),
                "extractions_remaining": max(0, 2 - extraction_counts[d.id]),
            }
            for d in data["documents"].values()
        ]
        observations = {
            "candidates": prioritize(
                candidates, self.request.objective, self.request.target_intake_year
            )
            if can_fetch
            else [],
            "document_count": len(data["documents"]),
            "documents": documents,
            "question_assessments": data["question_assessments"],
            "context_differences": data["context_differences"],
            "temporal_warnings": data["temporal_warnings"],
            "evidence_assessments": [
                {
                    "claim_id": c.id,
                    "field": c.field,
                    **{k: v for k, v in c.semantic_assessment.items() if k != "passage"},
                    "passage": c.semantic_assessment.get("passage", "")[:600],
                }
                for c in data["claims"]
                if c.semantic_assessment.get("label") != "fully_supported"
            ][:120],
            "previous_queries": [
                s.data["query"] for s in steps if s.node == "DISCOVER" and s.data.get("query")
            ],
            "extracted_windows": [s.data for s in steps if s.node == "EXTRACT"],
            "claims": [
                {
                    "field": c.field,
                    "value": c.value,
                    "state": c.state,
                    "scope": c.scope,
                    "evidence_id": c.evidence_id,
                }
                for c in data["supported"]
            ][:120],
            "missing_fields": sorted({x["field"] for x in data["missing"]}),
            "conflicts": [{"field": c.field, "summary": c.summary} for c in data["contradictions"]],
            "failed_sources": [
                {"url": s.url, "message": s.message}
                for s in data["sources"]
                if s.document_id is None
            ],
            "recent_events": [
                {"node": s.node, "summary": s.summary}
                for s in session.scalars(
                    select(ResearchStep)
                    .where(ResearchStep.run_id == self.run_id)
                    .order_by(ResearchStep.sequence.desc())
                    .limit(4)
                )
            ],
            "available_actions": ["stop"]
            + (["reextract"] if any(d["extractions_remaining"] for d in documents) else [])
            + (["fetch"] if can_fetch and candidates else [])
            + (["search"] if self.search else []),
            "stats": run.stats,
        }
        return observations

    def decide(self, state: WorkflowState) -> dict[str, Any]:
        self.budget.increment("iterations", self.request.limits.max_iterations)
        with self.sessions() as session:
            plans = list(
                session.scalars(
                    select(ResearchPlan)
                    .where(ResearchPlan.run_id == self.run_id)
                    .order_by(ResearchPlan.revision)
                )
            )
            observations = self.observations(session)
            current_plan = plans[-1].content
        decision = self.provider.generate(
            Decision,
            "DECIDE",
            {
                "objective": self.request.objective,
                "plan": current_plan,
                "observations": pack_observations(dict(observations)),
                "limits": self.request.limits.model_dump(),
            },
            self.budget,
        )
        rejected = None
        if decision.action not in observations["available_actions"]:
            rejected = "Selected tool is unavailable under this run's capabilities or budgets"
        elif decision.action == "fetch" and decision.target_id not in {
            c["id"] for c in observations["candidates"]
        }:
            rejected = "Fetch target must be an actual pending in-scope candidate ID"
        elif decision.action == "reextract" and decision.target_id not in {
            d["id"] for d in observations["documents"]
        }:
            rejected = "Re-extraction target must be a document already attached to this run"
        elif decision.action == "search" and not decision.query:
            rejected = "Search requires a nonempty query"
        elif decision.action == "search" and " ".join(
            (decision.query or "").casefold().split()
        ) in {" ".join(q.casefold().split()) for q in observations["previous_queries"]}:
            rejected = "This search query was already attempted; select a new investigation"
        elif decision.question_id and decision.question_id not in {
            q["id"] for q in current_plan["questions"]
        }:
            rejected = "Question ID must resolve to the current plan"
        if decision.action == "reextract" and any(
            d["id"] == decision.target_id and decision.window_start >= d["character_count"]
            for d in observations["documents"]
        ):
            rejected = "Re-extraction window must start inside the selected document"
        if decision.action == "reextract" and (
            any(
                d["id"] == decision.target_id and not d["extractions_remaining"]
                for d in observations["documents"]
            )
            or any(
                w.get("document_id") == decision.target_id
                and w.get("window_start", 0) == decision.window_start
                and w.get("question_id") == decision.question_id
                for w in observations["extracted_windows"]
            )
        ):
            rejected = (
                "Document extraction budget exhausted or identical focus/window already inspected"
            )
        if decision.revised_plan and not set(required_fields(plans)) <= {
            str(f) for q in decision.revised_plan.questions for f in q.fields
        }:
            rejected = "Plan revisions cannot drop original research fields"
        with self.sessions() as session:
            if rejected:
                self.event(
                    session,
                    "DECIDE",
                    "Rejected model tool selection: " + rejected,
                    state,
                    {"rejected": True, "action": decision.action},
                )
                return {"action": "invalid", "phase": "DECIDE"}
            if decision.revised_plan:
                session.add(
                    ResearchPlan(
                        run_id=self.run_id,
                        revision=len(plans) + 1,
                        content=decision.revised_plan.model_dump(mode="json"),
                    )
                )
            update = {**state, **decision.model_dump(exclude={"revised_plan"}), "phase": "DECIDE"}
            self.event(
                session,
                "DECIDE",
                decision.summary,
                update,
                {
                    "action": decision.action,
                    "target_id": decision.target_id,
                    "question_id": decision.question_id,
                    "query": decision.query,
                    "plan_revision": len(plans) + int(decision.revised_plan is not None),
                },
            )
        return {**decision.model_dump(exclude={"revised_plan"}), "phase": "DECIDE"}

    def fetch(self, state: WorkflowState) -> dict[str, Any]:
        self.budget.increment("tool_calls", self.request.limits.max_tool_calls)
        self.budget.increment("documents_examined", self.request.limits.max_documents)
        with self.sessions() as session:
            candidate = session.get(ResearchCandidate, state.get("target_id"))
            assert candidate and candidate.run_id == self.run_id and candidate.status == "pending"
            url = candidate.url
            cutoff = utcnow() - timedelta(seconds=self.settings.research_cache_seconds)
            cached = session.scalar(
                select(SourceDocument)
                .join(RunSource, RunSource.document_id == SourceDocument.id)
                .where(
                    RunSource.url == url,
                    SourceDocument.synthetic == (self.request.mode == "demo"),
                    SourceDocument.last_checked_at >= cutoff,
                )
                .order_by(SourceDocument.last_checked_at.desc())
                .limit(1)
            )
            if cached:
                try:
                    self.policy.validate(cached.url)
                except ResearchError:
                    cached = None
            cached_id = cached.id if cached and self.request.mode == "live" else None
            cached_url = cached.url if cached_id and cached else None
        try:
            if cached_id:
                # Cached reuse must still honor the source policy.
                if hasattr(self.fetcher, "check_robots"):
                    self.fetcher.check_robots(url, self.budget)
                    if cached_url and cached_url != url:
                        self.fetcher.check_robots(cached_url, self.budget)
                document = None
            else:
                document = self.fetcher.fetch(url, self.budget)
                document.url = self.policy.validate(document.url)
            self.budget.check()
            with self.sessions() as session:
                if cached_id:
                    row = session.get(SourceDocument, cached_id)
                    assert row
                else:
                    assert document
                    row = session.scalar(
                        select(SourceDocument).where(
                            SourceDocument.url == document.url,
                            SourceDocument.sha256 == document.sha256,
                            SourceDocument.synthetic == document.synthetic,
                        )
                    )
                    if row:
                        row.last_checked_at = utcnow()
                    else:
                        row = SourceDocument(
                            url=document.url,
                            title=document.title,
                            media_type=document.media_type,
                            sha256=document.sha256,
                            raw_content=document.raw,
                            text=document.text,
                            locations=document.locations,
                            links=document.links,
                            synthetic=document.synthetic,
                        )
                        session.add(row)
                        session.flush()
                candidate = session.get(ResearchCandidate, state.get("target_id"))
                assert candidate
                candidate.status = "fetched"
                session.add(
                    RunSource(
                        run_id=self.run_id,
                        document_id=row.id,
                        url=url,
                        status="cached" if cached_id else "retrieved",
                        cache_hit=bool(cached_id),
                    )
                )
                added = self.add_candidates(session, row.links, "link", row.id)
                prior_extractions = session.scalars(
                    select(ResearchStep).where(
                        ResearchStep.run_id == self.run_id, ResearchStep.node == "EXTRACT"
                    )
                )
                duplicate = any(s.data.get("source_hash") == row.sha256 for s in prior_extractions)
                self.event(
                    session,
                    "FETCH",
                    "Reused a versioned cached document; original verification date retained"
                    if cached_id
                    else "Retrieved and normalized source content",
                    {**state, "document_id": row.id},
                    {
                        "document_id": row.id,
                        "cache_hit": bool(cached_id),
                        "new_candidates": added,
                        "duplicate_content": duplicate,
                    },
                )
                return {"phase": "FETCH", "document_id": None if duplicate else row.id}
        except (BudgetExhausted, RunCancelled):
            raise
        except ResearchError as exc:
            with self.sessions() as session:
                candidate = session.get(ResearchCandidate, state.get("target_id"))
                assert candidate
                candidate.status = "failed"
                session.add(
                    RunSource(
                        run_id=self.run_id, url=url, status=exc.code, message=exc.message[:300]
                    )
                )
                self.event(session, "FETCH", exc.message, state, {"error_code": exc.code})
            return {"phase": "FETCH", "document_id": None}

    def extract(self, state: WorkflowState) -> dict[str, Any]:
        document_id = (
            state.get("target_id")
            if state.get("action") == "reextract"
            else state.get("document_id")
        )
        self.budget.check()
        if state.get("action") == "reextract":
            self.budget.increment("tool_calls", self.request.limits.max_tool_calls)
        with self.sessions() as session:
            prior = list(
                session.scalars(
                    select(ResearchStep).where(
                        ResearchStep.run_id == self.run_id, ResearchStep.node == "EXTRACT"
                    )
                )
            )
            if sum(s.data.get("document_id") == document_id for s in prior) >= 2:
                self.event(session, "EXTRACT", "Per-document extraction limit reached", state)
                return {"phase": "EXTRACT", "document_id": document_id}
            row = session.get(SourceDocument, document_id)
            assert row
            plan = session.scalar(
                select(ResearchPlan)
                .where(ResearchPlan.run_id == self.run_id)
                .order_by(ResearchPlan.revision.desc())
            )
            window_start = state.get("window_start", 0) if state.get("action") == "reextract" else 0
            result = self.provider.generate(
                Extraction,
                "EXTRACT",
                {
                    "objective": self.request.objective,
                    "plan": plan.content if plan else {},
                    "focus_question": state.get("question_id"),
                    "document": {
                        "id": row.id,
                        "text": row.text[window_start : window_start + 30_000],
                        "scope_context": row.text[:1000],
                        "window_start": window_start,
                        "total_characters": len(row.text),
                        "truncated": len(row.text) > 30_000,
                    },
                },
                self.budget,
            )
            for item in result.claims:
                existing = session.scalars(
                    select(ExtractedClaim).where(
                        ExtractedClaim.run_id == self.run_id,
                        ExtractedClaim.document_id == row.id,
                        ExtractedClaim.field == item.field,
                        ExtractedClaim.value == item.value,
                        ExtractedClaim.proposed_quote == item.quote,
                        ExtractedClaim.proposed_scope_quote == item.scope_quote,
                    )
                )
                if any(c.scope == item.scope.model_dump() for c in existing):
                    continue
                session.add(
                    ExtractedClaim(
                        run_id=self.run_id,
                        document_id=row.id,
                        field=item.field,
                        value=item.value,
                        scope=item.scope.model_dump(),
                        proposed_quote=item.quote,
                        proposed_scope_quote=item.scope_quote,
                        proposed_start=item.start,
                    )
                )
            self.event(
                session,
                "EXTRACT",
                "Recorded extraction candidates; verification is pending",
                {**state, "document_id": row.id},
                {
                    "document_id": row.id,
                    "candidate_count": len(result.claims),
                    "input_truncated": len(row.text) > 30_000,
                    "window_start": window_start,
                    "question_id": state.get("question_id"),
                    "source_hash": row.sha256,
                },
            )
        return {"phase": "EXTRACT", "document_id": document_id}

    def verify(self, state: WorkflowState) -> dict[str, Any]:
        self.budget.check()
        with self.sessions() as session:
            counts = verify_claims(session, self.run_row(session))
            self.event(
                session,
                "VERIFY",
                "Checked exact support/scope spans and compared supported "
                "values; missing information remains unknown",
                state,
                counts,
            )
        return {"phase": "VERIFY"}

    def finish(self, reason: str, status: str = "completed", error: str | None = None) -> None:
        with self.sessions() as session:
            run = self.run_row(session)
            if run.cancel_requested and status != "failed":
                reason, status = "cancelled", "cancelled"
            report = build_report(session, run, reason)
            run.status, run.outcome, run.stop_reason, run.error = (
                status,
                report["outcome"],
                reason,
                error,
            )
            run.finished_at = run.updated_at = utcnow()
            run.state = {**run.state, "phase": "REPORT", "action": "stop"}
            current = session.get(ResearchReport, self.run_id)
            if current:
                current.content = report
            else:
                session.add(ResearchReport(run_id=self.run_id, content=report))
            self.event(
                session,
                "REPORT",
                "Stored the evidence-led report with explicit limitations",
                run.state,
                {"outcome": report["outcome"], "stop_reason": reason},
            )

    def report(self, state: WorkflowState) -> dict[str, Any]:
        self.budget.check()
        self.finish("model_stop")
        return {"phase": "REPORT"}

    def execute(self) -> None:
        with self.sessions() as session:
            transitioned = session.scalar(
                update(ResearchRun)
                .where(
                    ResearchRun.id == self.run_id,
                    ResearchRun.status == "pending",
                    ResearchRun.cancel_requested.is_(False),
                )
                .values(status="running", started_at=utcnow(), updated_at=utcnow())
                .returning(ResearchRun.id)
            )
            session.commit()
            if transitioned != self.run_id:
                self.fetcher.close()
                return
        graph = StateGraph(WorkflowState)
        for name in ("plan", "discover", "fetch", "extract", "verify", "decide", "report"):
            graph.add_node(name.upper(), getattr(self, name))
        graph.add_edge(START, "PLAN")
        graph.add_edge("PLAN", "DISCOVER")
        graph.add_edge("DISCOVER", "DECIDE")
        graph.add_conditional_edges(
            "DECIDE",
            lambda s: {
                "fetch": "FETCH",
                "search": "DISCOVER",
                "reextract": "EXTRACT",
                "stop": "REPORT",
            }.get(s.get("action", "stop"), "DECIDE"),
        )
        graph.add_conditional_edges(
            "FETCH", lambda s: "EXTRACT" if s.get("document_id") else "DECIDE"
        )
        graph.add_edge("EXTRACT", "VERIFY")
        graph.add_edge("VERIFY", "DECIDE")
        graph.add_edge("REPORT", END)
        try:
            # Disable third-party tracing even when configured in the ambient environment.
            with tracing_context(enabled=False):
                graph.compile().invoke({"run_id": self.run_id}, {"recursion_limit": 100})
        except RunCancelled:
            self.finish("cancelled", "cancelled")
        except BudgetExhausted as exc:
            self.finish(exc.code)
        except ResearchError as exc:
            self.finish(exc.code, "failed", exc.message)
        except Exception:
            # Do not expose raw exceptions, provider bodies, or credential-bearing URLs.
            self.finish(
                "internal_error",
                "failed",
                "Research execution failed; preserved artifacts are available for inspection",
            )
        finally:
            self.fetcher.close()
