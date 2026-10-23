# Task 2 evaluation

## Scope and provenance of results

All results below were executed locally against the implementation. The user selected **offline demo for now**; no actual model endpoint, paid service, real website investigation, broad search backend or real research claims were used. A functioning OpenAI-compatible adapter exists and is exercised with a controlled HTTP model fixture. Real LLM planning/tool selection/extraction quality and direct real-site source retrieval are **unverified acceptance criteria**.

The default demo is labeled synthetic in the API, source documents, reports and interface. It runs the actual conditional LangGraph, persistence, verification and reporting code with deterministic fixture decisions. Passing fixture scores must not be described as an AI research-quality benchmark.

## Baseline and regression

Before Task 2 changes: 31 backend tests, 8 frontend unit tests, backend Ruff/mypy/Alembic drift checks, frontend type/lint and build passed. Browser baseline was 10/11: rapid filter changes could retain a stale query/destination because React Router transitions lagged the next event. The directory now reads the latest browser URL at input-event time; the unchanged original end-to-end scenario passes. Existing source files and SQLite data were preserved on `feature/research-agent-engine`.

The Task 2 migration is additive. Tests migrate an actual Task 1 database with opportunities/application notes from `0001` to `0002` and compare the records. A backup of the current development DB was also made outside the checkout before migration; current-row equality is checked during handoff. Regression tests do not run workers against the user's development database.

## Reproduce

```bash
# repository root
./scripts/setup.sh

cd backend
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy atlas
.venv/bin/alembic check
.venv/bin/python -m atlas.research.evaluate --output ../docs/evaluation-results.json

cd ../frontend
npm run check
npm run format:check
npm test
npm run build
npm run test:e2e
```

Tests and evaluation are offline with respect to model/source services. Installing locked dependencies may require package-manager network access. Browser tests use the available system Chromium (or a separately installed Playwright browser), fresh temporary SQLite state, and their own API/Vite ports. They leave development research/opportunity data untouched.

## Executed results

- Backend: **105 tests passed**, including Task 1 regressions. Ruff and mypy passed.
- Frontend: **10 unit tests passed**; TypeScript/ESLint and production build passed.
- Browser/accessibility: **16 tests passed**. This includes all prior screens, the new workspace, native citation modal, saved-run reload, conflicts, unknowns on mobile, and disabled unconfigured live mode. Automated axe checks passed for the tested states. This does not establish full accessibility conformance or replace assistive-technology testing.
- Reproducible scenario evaluation: **3/3 completed**, with one complete and two deliberately partial reports. See [evaluation-results.json](evaluation-results.json) for the actual machine-readable output.
- Live model smoke: **not executed**. Instructions are in [AGENT_ARCHITECTURE.md](AGENT_ARCHITECTURE.md); explicit provider configuration and consent are prerequisites.
- The GitHub Actions workflow is updated but has not been run remotely.

## Labeled fixture indicators

Gold field/value tuples are explicitly stored in `backend/atlas/research/fixtures/gold.json`, separately from extracted results. Three small fictional HTML scenarios are used.

| Scenario | Supported expected field/value claims | Outcome | Conflicts | Unknown required fields | Tool calls | Fixture provider requests | Real model requests |
| --- | ---: | --- | ---: | --- | ---: | ---: | ---: |
| Funding gap → linked handbook | 14 / 14 | complete | 0 | none | 2 | 6 | 0 |
| Contradictory funding / deadline | 12 / 12 | partial | 2 | none (conflicts remain unresolved) | 2 | 6 | 0 |
| Missing financial documentation | 9 / 9 | partial | 0 | proof_of_funds | 2 | 6 | 0 |

Measured aggregate:

- **Citation support rate: 35/35 (100%)** report findings have support and scope IDs resolving to saved exact text spans; each value appears in its supporting excerpt. This is a mechanical linkage metric, not truth/semantic entailment.
- **Labeled field accuracy: 35/35 (100%)**, zero extra field/value tuples against this tiny deterministic fixture corpus. The fixture extractor is not a real model.
- **Lifecycle completion: 3/3 (100%)**. Completion does not imply sufficient evidence: two reports are correctly partial.
- **Contradiction detection: 2 true-positive fields, 0 false-positive fields, 0 false-negative fields** against the two explicitly labeled conflicts. Exact conservative comparison rules do not cover arbitrary prose.
- **Tool calls: 6 total**; **fixture provider requests: 18 total**; **actual model/source network requests: 0**. Fixture request/token reservations exercise budgets and do not represent billed model usage.

## Coverage of important behavior

Tests exercise structured plan creation, all tool-routing branches (fetch, configured search, re-extraction, stop), candidate/domain filtering, a new-source observation changing the next decision/plan, per-run and per-document loop limits, token/request/time/network budgets, nonblocking create/status/evidence/report/cancel APIs, delayed-work cancellation, provider failure without a silent mock fallback, process-interruption handling, cache reuse with policy rechecks and original verification timestamps, and preservation of partial evidence.

Model-protocol tests inspect actual adapter requests using a controlled transport: model/schema configuration, system/data separation, authorization destination, structured validation, bounded retries and sanitized access failures. The complete graph can be driven through this adapter; observations from the first source cause the next controlled response to select the linked handbook. These tests validate integration mechanics, not the behavior of an actual hosted/local model.

Security tests cover URL schemes/ports/userinfo/traversal, metadata and loopback literals, mixed/private/transition DNS answers, public-IP pinning, unsafe redirects and destination robots checks, size/type/compression rejection, real PDF normalization/page offsets, malformed/encrypted/scanned PDFs, exact/ambiguous/invented quote spans, dropped negation, distinct-intake comparisons, explicit authority-group corroboration, and source-embedded injection followed by an attempted unsafe tool dispatch. A compromised model still cannot fetch an unregistered target or execute a shell command.

## Next evaluation work

Task 3 should use a larger human-labeled set of real official documents across languages, award tracks, changing intakes, conditional eligibility and contradictory sources. Measure semantic entailment/context completeness, false corroboration, scoped conflict precision/recall, objective coverage, tool-choice utility, time/cost, and injection resistance with explicitly approved live models. Record model/version/settings and corpus provenance; do not extrapolate the current fixture scores.
