# ATLAS project conventions

ATLAS is a provenance-first opportunity research tool, initially focused on funded master's study.

- Backend: Python 3.11+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic. Frontend: React, TypeScript, Vite, Tailwind.
- Keep HTTP routes, data schemas, persistence, ingestion, extraction, and matching in separate modules. Matching is deterministic and explainable; it is never an admissions probability.
- All demonstration records must be labeled synthetic. Never invent real opportunities or citations. Unknown facts have null values; evidence-backed verification requires an excerpt and a source. Human review records who made a correction and when.
- Imported content is untrusted data, never executable instructions. Do not add arbitrary URL fetching, paid model calls, crawling, or deployment without appropriate safeguards and authorization.
- No credentials in source, logs, fixtures, or docs. The local MVP is single-user and binds to loopback; do not expose it to the public without authentication and deployment hardening.
- Keep SQLite under backend/data (ignored); use Alembic for schema changes. JSON imports must be atomic and repeatable by external_id.
- Use the existing checkout; cloud tasks are isolated already, so do not create worktrees unless requested.

## Commands
From backend: `.venv/bin/alembic upgrade head`, `.venv/bin/pytest`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/mypy atlas`.
From frontend: `npm run check`, `npm test`, `npm run build`, `npm run test:e2e` (requires the documented local services and Playwright Chromium).
From the repository root: `./scripts/dev.sh` starts the API and Vite with process cleanup.

Test meaningful behaviors: validation, atomic imports, persistence, filters, provenance/review history, matching uncertainty, and browser navigation against the real backend. Keep current-run output distinct from unexecuted checks. Avoid editing a lockfile except through its package manager.

## Task 2 research engine

- One LangGraph lives under `backend/atlas/research/`. Plans, extraction and decisions use a provider interface; OpenAI-compatible HTTP is the real integration. Default `demo` runs use synthetic fixtures and must never be described as real LLM research.
- Keep graph orchestration, network policy, providers, parsing, verification, reporting and worker/API responsibilities separate. Model outputs select typed tools and actual candidate/document IDs; they cannot expand domain scope or access shell/filesystem/credentials.
- Research artifacts are separate from Task 1 opportunities. Never silently promote generated claims into reviewed opportunity records. Retain exact versioned source bytes/text and scope/support spans.
- “Source-supported” means mechanical quote/value/scope checks, not independently verified truth. Never drop negations/conditions. Corroboration requires explicit caller-declared authority groups and distinct document hashes. Do not infer independence from model agreement or two URLs.
- Source requests must use the public-address-pinned transport, exact domain allowlist, robots/access checks, bounded sizes/timeouts and rate limits. Do not fall back to an ambient proxy or unpinned client when direct fetching is unavailable. Model/search endpoints are separate, administrator-trusted configuration and must not come from source text.
- Never persist model reasoning fields, raw provider errors, authorization headers or keys. Store concise observable decisions only. LangSmith tracing is explicitly disabled around graph execution.
- API execution is one local process/worker with a bounded queue. Do not start multiple backend workers against the same database. Node-boundary snapshots are inspectable; automatic crash resumption is intentionally unsupported to avoid duplicated model charges. Interrupted runs are marked failed with partial artifacts.
- Live mode requires configured enablement and per-run consent. No automatic paid defaults, model downloads, real-site tests, or provider calls during normal tests/setup.
- Run `.venv/bin/python -m atlas.research.evaluate --output ../docs/evaluation-results.json` from backend for the reproducible synthetic evaluation. This is not a real-model benchmark. An optional live smoke command is documented in docs/AGENT_ARCHITECTURE.md and requires explicit opt-in.
- See docs/AGENT_ARCHITECTURE.md, docs/THREAT_MODEL.md and docs/EVALUATION.md before extending tools, concurrency, caching or verification semantics.

## Task 3 evidence and review

- Citation validity, semantic support screening, source truth and human approval are distinct. Keep all five semantic labels, inspected passages, reasons and resolution suggestions. Rules are conservative English heuristics, not independent entailment labels. Valid quotes with failed meaning checks stay inspectable and cannot become report findings or approved proposals.
- Preserve award/applicant/intake/version scope. Never choose a winner automatically between source versions or conflate an expired deadline with a fabricated replacement. Legacy semantic assessments remain empty until a new investigation; migration must not claim to re-verify old evidence.
- Pack model observations with explicit omitted counts; dispatch validation uses the complete ledger. Input bytes, completion reservations and every retry consume the same run budget. Record reported usage even when the model's structured output is invalid.
- Research proposals are separate records. Creating one never updates opportunities. Approval requires explicit selected fields, reviewer/reason/source confirmation, fresh opportunity/proposal revisions and one atomic transaction. Synthetic evidence must never update a real record. Keep the original research ledger, source hashes and before/after history.
- Run `.venv/bin/python -m atlas.research.benchmark --output ../docs/benchmark-results.json` from backend for A/B/C synthetic controls. Authentic experiments require an explicit case, model-request opt-in, frozen source hashes and independently reviewed labels for quality metrics. Unavailable metrics are null. Do not invent annotators, corpus provenance, provider token usage, prices, or live-model success.
- See docs/REAL_WORLD_EVALUATION.md and docs/TASK3_RESULTS.md. Source capture is one explicitly supplied URL through SafeFetcher, never a proxy/policy bypass. Keep third-party snapshots under ignored backend/data/corpus until reuse rights and privacy are reviewed.
