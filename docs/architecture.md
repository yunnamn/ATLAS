# Architecture and trust boundaries

This document describes the Task 1 manual opportunity workflow. Task 2 adds a separate research engine: see [AGENT_ARCHITECTURE.md](AGENT_ARCHITECTURE.md), [THREAT_MODEL.md](THREAT_MODEL.md), and [EVALUATION.md](EVALUATION.md). Research artifacts do not silently update reviewed opportunities.

Task 3 adds an explicit proposal/approval bridge: [REAL_WORLD_EVALUATION.md](REAL_WORLD_EVALUATION.md). Proposal creation is isolated from directory writes; only selected, reviewed changes commit with evidence and optimistic revision checks. Original-text eligibility, language and obligation fields remain separate from the numeric matching rules.

## Request flow

React pages → `/api` (Vite proxy) → FastAPI routes → Pydantic validation → storage / extraction / matching services → SQLAlchemy → SQLite.

Routes orchestrate; the database module has no UI logic. Extraction returns unverified candidates and never saves implicitly. Storage imports entire validated batches in one transaction; existing external IDs are skipped to protect edits. Matching reads typed records/profile data and returns explanations without changing them. No crawler, scheduler, model API, or external application integration runs in this manual workflow. The separate Research Agent has an explicit, disabled-by-default model integration.

## Persistence

| Entity | Responsibility |
| --- | --- |
| opportunities | Stable external ID; indexed title/country/category; JSON document with source registry and facts; revision and timestamps |
| changes | Append-only application-level audit events with actor, reason, before/after snapshots, revision, and timestamp |
| profiles | One local user's education, nationality, constraints, interests, and preferences |
| applications | Unique opportunity link, stage, notes, missing requirements, update timestamp |
| alembic_version | Explicit migration state |

Fact/source documents are nested JSON to keep import validation and the evolving opportunity schema coherent. External IDs are unique. Review changes use SQLAlchemy optimistic concurrency (`revision` as version ID). The API rejects stale edits. JSON updates replace the complete document to ensure SQLAlchemy tracks changes. Import validation occurs before any inserts; database failures roll back the transaction. Snapshot history is intentionally simple for small local libraries; later versions should add retention and indexed claim entities for large datasets.

Source records carry optional HTTP(S) URLs, retrieval dates (unknown when not supplied), document hashes, and importer-asserted official status. Upload hashes cover the original bytes, not reconstructed text. Server-side creation/update timestamps record ingestion and corrections separately. Original PDF files are not retained and source URLs are not fetched. Date-only deadlines have no inferred closing hour or timezone.

Opportunity categories (`masters`, `fellowship`, `hackathon`, `job`) reserve extension points. Master's matching is the initial evaluator; do not treat it as a complete evaluator for other categories. Future category-specific rule sets should implement independent evaluators.

## Meaning of verification

- **unknown**: null value. Absence is recorded, not silently completed.
- **unverified**: a recorded value awaiting source review; it may have supporting text.
- **verified** (UI: “Reviewed · evidence linked”): a human supplied a source and excerpt and recorded a correction. The application validates linkage, not truth or institutional endorsement. Imported reviewed records rely on the importer's assertion; the initial audit event records `import` as actor.

The local reviewer name is a label, not an authenticated identity. Audit history is append-only through the API, not tamper-proof against direct database edits. Synthetic records retain their synthetic identity through reviews.

## Matching v1

Academic requirements are separate checks for nationality, minimum GPA, required degree, and IELTS. Omitted profile or rule data produces `unknown`. Unverified rules produce provisional matches/gaps. A reviewed failed rule produces `requirement_gap`; all four reviewed checks must pass for `rules_met`, which refers only to these recorded rules. Complex conditions and unmodeled requirements always need manual review. Nationality rules are evaluated only for `all` or explicit comma-separated two-letter codes. Prose is unknown to the evaluator. A highest master’s degree does not prove a prior bachelor’s degree; that check stays unknown until clarified.

Preference fit uses exact case-insensitive comparisons: preferred destination = 35 points, overlapping subject tags = 35, tuition-and-stipend claim = 30 if requested. Disable empty destination/subject preferences and the disabled funding constraint from the denominator. Unknown funding stays in the enabled denominator and earns zero points. With no enabled preference, the score is null. A score of 100 can coexist with a hard eligibility gap. Unverified funding can contribute to preference fit; inspect its fact state before relying on it. This score is never an admissions probability or a ranking of academic merit.

Risk flags cover application fees, proof of funds, return obligations, and incomplete/unknown tuition-and-living support. Tuition-and-stipend alone does not establish travel, insurance, visa, deposits, family support, or total cost coverage. Those facts remain separately inspectable.

## Untrusted input and extraction

- Never execute HTML, scripts, PDF actions, or source instructions. React renders source text as escaped content. URLs use Pydantic HTTP(S) types and open with `noreferrer`.
- JSON inputs reject unexpected fields, unknown fact keys, invalid dates, invalid numeric bounds, missing evidence links, duplicate source IDs, inconsistent null/state values, and duplicate IDs within a batch.
- PDF input: at most 8 MiB, PDF header required, separate Python subprocess, 12-second wall timeout, 8-second CPU limit, 512-MiB address-space limit, 30-page limit, 100,000 extracted-character limit, encrypted/unreadable/scanned PDFs rejected. These limits are a local defense, not a hardened public document-processing sandbox. Add OS/container isolation and request size/rate limits before hosting.
- Deterministic extraction recognizes only exact English labeled lines: `Deadline`, `Funding`, `Minimum GPA`, `IELTS`, `Proof of funds`, `Return obligation`. Duplicate exact matches are omitted. Invalid candidate values are discarded through the import validator. It does not semantically interpret arbitrary prose.
- `ExtractionProvider` is the optional provider-independent adapter boundary. No provider is configured and no credentials are needed. Future remote adapters must be opt-in, validate schemas and evidence, preserve original provenance, and disclose third-party costs/data handling.
- In the manual import workflow, URL retrieval is not performed. The Research Agent now implements scoped retrieval; additional public-hosting hardening is required. The original requirements were: network isolation can prevent SSRF (including rebinding, redirects, IPv6, and private destinations), enforce size/time/type limits, honor access restrictions, and record content snapshots. Storing a manual citation URL does not establish successful access or official ownership.

## Database portability

The initial migration uses SQLAlchemy portable column types and generic JSON, with no SQLite-specific query SQL. To experiment with PostgreSQL: add an explicit `psycopg` optional dependency, install it through uv, configure `ATLAS_DATABASE_URL=postgresql+psycopg://...` securely, then run Alembic against a fresh database. SQLite data is not automatically copied; write and validate an explicit export/import migration. Test migrations, locking/concurrency, JSON, timestamps, indexes, and collation on PostgreSQL before claiming support. For larger libraries, normalize claims or use JSONB indexes and move all filtering/pagination into database queries.

## Local runtime

Bash scripts use the existing checkout and fail on errors. Retained dependencies and SQLite state survive service restarts. API/Vite processes must be started again in a fresh task. Vite reads `ATLAS_API_PROXY` only for the development proxy; it is not a browser credential. SQLite URLs are relative to `backend/`. No paid calls, purchases, external messages, bulk crawling, deployment, or publication are performed.
