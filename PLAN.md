# ATLAS implementation plan

## 1. Trustworthy vertical slice (required)
- Build FastAPI / SQLAlchemy storage with Alembic migrations and validated import schemas.
- Store explicit known, unknown, and unverified claims, source excerpts, timestamps, and revisions.
- Expose create, import, list, filter, and detail endpoints; seed only clearly synthetic records.
- Build a responsive React dashboard, searchable directory, detail/evidence views, and review workflow.
- Acceptance: a fresh SQLite database migrates; demo import is repeatable; frontend uses the real API; search/filter/detail and corrections work.
- Verification: `cd backend && .venv/bin/pytest`; `cd frontend && npm run check && npm test && npm run build`; browser smoke tests against live services.

## 2. Personal workflow (in this implementation if feasible)
- Persist a local user profile, explainable compatibility rules, shortlist, statuses, and missing requirements.
- Keep hard eligibility checks distinct from preferences. Missing information is never a pass, and the score is never an admissions probability.
- Acceptance: profile edits affect explanations; applications survive restarts; compare opportunities side by side.

## 3. Incremental ingestion and future research
- Support reviewed structured JSON import first, then local PDF/text extraction with conservative deterministic rules.
- Add URL retrieval only with public-network isolation, bounded downloads, access-policy handling, and adversarial tests. Do not fetch arbitrary URLs casually.
- Define an optional, provider-independent model extraction boundary; disable it by default. No paid calls.
- Scheduled source monitoring, accounts, and PostgreSQL deployment remain later milestones.

## Completion gate
Document exact startup commands, tradeoffs, and limits. Run meaningful automated tests and a real API/browser workflow, report failures honestly, inspect the final diff, and leave working source code with no credentials.

## Implementation status

- Milestone 1: complete. Local FastAPI/SQLite/Alembic + React application, validated synthetic imports, search/filter/detail, evidence corrections and history, and documented startup.
- Milestone 2: complete for the scoped local MVP. Profiles, deterministic matching, financial risk flags, comparisons, persisted shortlist/application status/notes/missing requirements.
- Milestone 3: local PDF/text candidates and extraction-provider protocol implemented. Safe website retrieval, actual model adapters, OCR, and scheduled source diffs are deferred explicitly.
- Final verification: 31 backend tests, 8 frontend tests, 11 live browser/accessibility tests passed; lint/type/format/build/schema checks passed. See docs/verification.md for scope and limitations.

# Task 2 — Research agent engine

## Baseline (before Task 2 changes)
- Task 1 API/storage/import/matching and six React screens are operational.
- Backend: 31 tests, Ruff, mypy, Alembic drift check passed. Frontend: 8 unit tests, type/lint and production build passed.
- Browser baseline: 10/11 passed. Clearing filters immediately followed by a funding selection retained a stale filter; fix and retain regression coverage.
- Existing data/source files are preserved on feature/research-agent-engine. No model endpoint or credentials are present; the user selected offline demo verification. Real provider integration will be implemented, with live model acceptance explicitly unverified.

## P1 — Bounded agent core
- Typed plans, actions, extraction candidates, evidence and reports; one LangGraph with PLAN/DISCOVER/FETCH/EXTRACT/VERIFY/DECIDE/REPORT and conditional feedback.
- OpenAI-compatible structured-output provider, disabled by default; observable decisions, validated tool arguments, retries/timeouts/request and token budgets.
- Public-address-pinned HTTP(S), explicit domain scope, redirect/robots controls, bounded HTML/PDF normalization, cached versioned documents.
- Deterministic verification of exact quote/scope spans; conservative conflict detection; explicit missing fields. No automatic promotion into opportunity records.
- Acceptance: observations change decisions; a second source can resolve or expose a gap; all claims in reports resolve to stored evidence; budgets/cancellation stop safely.

## P2 — Persistence and API
- Backward-compatible migration for runs, versioned plans, events/checkpoints, documents, snippets, claims, contradictions and reports.
- Nonblocking local worker, lifecycle/status/evidence/report/cancel endpoints; preserve partial results. Interrupted workers are marked interrupted, not falsely resumable.

## P3 — Research workspace
- Objective/seeds/scope form, honest demo/live modes, progress polling, plan, citations, source inspection, report, cancellation, responsive navigation.

## P4 — Evaluation and handoff
- Offline model/transport fixtures, provider protocol tests, network/security tests, branching/conflict/uncertainty/budget/cancellation/failure scenarios, migration preservation and Task 1 regressions.
- Run pytest/Ruff/mypy, frontend type/lint/unit/build/browser/axe checks. Publish measured fixture metrics only. Document architecture, threat model, configuration, offline demo and opt-in live smoke test.

## Task 2 completion evidence

- Implemented the conditional LangGraph, real opt-in OpenAI-compatible adapter, optional SearxNG discovery adapter, DNS-pinned scoped HTML/PDF tools, exact-span verification, conservative conflict handling and bounded feedback/re-extraction.
- Added migration 0002, versioned research/evidence storage, one local worker, lifecycle/progress/evidence/report/cancel API, cache/policy handling and interruption behavior.
- Added the Research Agent workspace, citation/source inspector, plan revisions/events, conflict/unknown reports, cancellation controls and explicit demo/live separation. Fixed the observed Task 1 filter race.
- Final automated checks: 105 backend tests, 10 frontend unit tests, 16 browser/accessibility tests; lint/type/format/build/schema checks passed. Three offline scenarios measured against separately labeled gold data; actual results are in docs/evaluation-results.json.
- User chose offline verification. Real-provider HTTP protocol mechanics are tested with controlled responses; actual real-model semantic planning/tool selection and real-site connectivity remain unverified. No paid/model calls, unrestricted crawling, deployment or publication were performed.
- Existing Task 1 database rows were compared with the pre-migration snapshot and remain unchanged. New research artifacts stay in separate tables. See docs/AGENT_ARCHITECTURE.md, docs/THREAT_MODEL.md and docs/EVALUATION.md for complete operating instructions and limits.

# Task 3 — Evidence quality and defensible evaluation

## Baseline and preservation
- Task 2 source verified at `9e22afc`; clean checkout, personal `yunnamn/ATLAS` remote. Work continues on `feature/research-intelligence`.
- Before changes: 105 backend tests, 10 frontend unit tests and 16 browser/accessibility tests passed; frontend type/lint/build passed. Existing SQLite backed up outside Git before additive migration.
- No model endpoint is configured. Continue the user's offline preference; do not perform billable inference. Real-model quality cannot be validated here.

## Milestones and acceptance
1. Add exact-span-preserving, conservative semantic assessments (five support labels), contextual scope dimensions, question-level evidence sufficiency and ranked candidate explanations. Reject redundant searches/extractions and record explicit uncertainty. Acceptance: adversarial context/negation/staleness and scope/version tests; Task 2 regressions pass.
2. Add reproducible A supplied-document / B fixed retrieval / C adaptive graph experiments with frozen corpus manifests, provenance, annotation gates, null unmeasurable metrics, token/cost/latency accounting and failure analysis. Keep synthetic controls separate from authentic unannotated documents. Acceptance: run all three offline controls; no manufactured human labels or real-model scores.
3. Add persisted proposed changes, citation inspection, selected-field approval, transactional application and stale-revision protection. Acceptance: no opportunity is changed before explicit approval; synthetic labels and original evidence survive; conflicting/unsupported findings cannot become verified records; browser review works.
4. Run full backend/frontend/browser/security/migration/evaluation checks, document actual results and remaining prerequisites, inspect source-only Git diff, commit and synchronize the personal feature branch.

## Verification
`cd backend && .venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy atlas && .venv/bin/alembic check`

`cd frontend && npm run check && npm run format:check && npm test && npm run build && npm run test:e2e`

Offline evaluation and benchmark commands will be recorded with their measured output. Live requests remain opt-in; independent real-document annotations and an approved model are prerequisites for defensible model comparisons.

## Task 3 completion evidence
- Implemented five-label bounded support screening with independent exact citations, explicit uncertainty/resolution, question-level coverage, award/applicant/intake/version comparisons, source priorities and expired-date advisories. General semantic entailment and real-model planning quality remain unverified.
- Added cumulative input budgets, usage retention for invalid outputs, truncated-response handling, bounded decision observations with full-ledger dispatch, and duplicate query/window/content controls.
- Implemented A/B/C frozen-corpus experiments with provenance/hashes, prediction spans, observable traces, raw/screened extraction metrics, annotation gates, null unknown metrics, usage/cost/latency and failure analysis. Nine synthetic runs measured A 27/35, B 35/35, C 35/35; no agent advantage over curated fixed retrieval. Eighteen authored semantic controls passed.
- Added migration 0003, proposal APIs, selected-field human approval in one transaction, stale/duplicate/conflict/synthetic guards, source inspection and desktop/mobile review UI. Original prose requirements have dedicated directory fact keys.
- Final checks passed: 153 backend tests, Ruff/format/mypy (31 application files), 10 frontend unit tests, TypeScript/ESLint/Prettier/build and 18 Chromium browser/axe tests. Task 2 three-scenario evaluation passed again. No model calls were made.
- Repeat setup and documented dev script worked. Health, Vite/API proxy, disabled live capabilities, new metadata and legacy review endpoints passed a live local smoke. Alembic drift check passed. All original rows/columns in 14 existing tables match the external pre-Task 3 backup; no original records were altered.
- Official Erasmus page capture failed with public DNS resolution failure. No authentic corpus or independently reviewed labels were obtained; no network-policy workaround or paid inference was attempted. Real-source/model acceptance remains open.
- Startup draft updated for Task 3; this does not publish a snapshot or prove fresh-task restoration. See docs/TASK3_RESULTS.md and docs/REAL_WORLD_EVALUATION.md for measured evidence, operating instructions and Task 4 priorities.
