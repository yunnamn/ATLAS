# ATLAS

**Opportunity intelligence, grounded in evidence.**

ATLAS is a working, local research workspace for students and early-career professionals. The first release focuses on funded master's study: discover opportunities, inspect citations, compare conditions, understand compatibility, and manage applications.

Task 2 adds a **Research Agent workspace** with a conditional LangGraph, persisted plans/events/evidence/reports, a real configurable OpenAI-compatible provider, scoped source tools, and a default **deterministic offline demo**. No actual model endpoint was used during implementation; live model quality and real-site connectivity remain unverified. See [agent architecture and configuration](docs/AGENT_ARCHITECTURE.md), [threat model](docs/THREAT_MODEL.md), and [executed evaluation](docs/EVALUATION.md).

Task 3 adds question-level evidence sufficiency, five separate support-screen labels, award/applicant/version scope, duplicate-work and input-budget controls, reproducible A/B/C experiments, and an explicit **Review changes** workflow that saves only human-approved fields. See [Task 3 operating and evaluation guide](docs/REAL_WORLD_EVALUATION.md) and [measured results](docs/TASK3_RESULTS.md). Synthetic controls passed; real-model research quality remains unverified and the attempted official-source capture was blocked at public DNS resolution.

All six bundled opportunities, institutions, rules, and excerpts are **synthetic demonstrations, not real awards**. ATLAS does not recommend applying to these examples. Real research enters through explicit user imports; missing information stays unknown.

## Run locally

Requirements: Python 3.11+, Node 22.12+ (Node 24 recommended), npm, [uv](https://docs.astral.sh/uv/). Tested with Python 3.12 and Node 24 on Linux. PDF parsing uses Linux/macOS resource limits; the cloud environment is Linux.

```bash
cd /workspace/ATLAS   # or your clone directory
./scripts/setup.sh
./scripts/dev.sh
```

The setup script installs locked dependencies, runs Alembic migrations, and imports the synthetic examples. It is repeatable: existing IDs are skipped, preserving corrections and application records. The dev script starts the API on loopback port **8000** and React/Vite on loopback port **5173**; Ctrl-C stops both. Open port 5173 in your local browser. No API keys, paid services, container runtime, or external database are required for the core app and offline research demo. Use one backend process; research execution is local and does not automatically resume after a crash.

For an empty research library, replace the final seed step with migration only, or use a separate database with `ATLAS_DATABASE_URL`. To run the services individually:

```bash
# Terminal 1
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m atlas.seed  # optional synthetic collection
.venv/bin/uvicorn atlas.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2, from the repository root
cd frontend
npm run dev -- --port 5173 --strictPort
```

On Windows use the equivalent `.venv/Scripts/` commands. PDF extraction is currently supported on Unix systems only; structured JSON and text extraction remain portable. The supplied shell scripts require Bash.

Vite forwards `/api` to port 8000; the browser really reads and writes the backend. The default database is `backend/data/atlas.db`, ignored by Git. All backend commands must run from `backend/` so the relative database URL resolves consistently. Copy `backend/.env.example` to `backend/.env` only to override defaults. Never commit the database, `.env`, or credentials. Health is available at `/api/health` on the backend; interactive OpenAPI documentation is at `/docs` on port 8000.

## Demo walkthrough

1. **Overview** shows the library, recorded funding claims, application counts, and unreviewed research. Every demo card carries a synthetic label.
2. **Discover opportunities** searches program names, institutions, destinations, summaries, and subject tags. Filter by destination or funding. Select two or three records to compare fees, funding, deadlines, and conditions side by side.
3. **Opportunity detail** separates recorded values from verification states. Expand any field to read the supporting excerpt and source. Missing facts display **Unknown**, never an inferred answer.
4. **Review / correct** lets you edit a fact, attach an existing source and excerpt, and record a reviewer and reason. Every correction creates a revision with before/after snapshots. Concurrent stale revisions receive a 409 rather than overwriting a correction. Reviewing synthetic evidence does not make it real.
5. **Profile & preferences** accepts nationality, degree, GPA, IELTS, interests, destinations, and a tuition/living funding constraint. Detail pages explain requirement checks separately from preference fit. Nothing is an admissions probability.
6. **Save opportunity** adds a record to **My applications**. Manage its stage, private notes, and missing requirements. Changes persist across reloads and backend restarts.
7. **Sources & verification** shows the review queue. **Import source** accepts a record, array, or `{ "opportunities": [...] }` batch. Use “Load one synthetic example” to inspect the schema, or import the complete collection. Duplicate IDs are skipped, never overwritten.
8. **PDF / source text** extracts conservative candidates, then opens editable record JSON. Complete the identity fields and review candidates before saving. Text and PDFs are processed locally; no document is sent to a model provider.


9. **Research agent** accepts an objective and optional official seed URLs in configured live mode. Start with **Offline synthetic demo**: inspect the plan, the decision to follow a newly discovered funding link, exact saved quotations, and the report. Switch scenarios to see conflicting statements or a retained unknown. The fixture demo does not investigate arbitrary real objectives. Live mode is disabled until explicitly configured and consented to; it may send source excerpts to a provider with separate costs.

10. **Review changes** on a finished investigation prepares a proposed new record or update. Inspect before/after values, support/scope quotations and saved sources; choose fields, enter a reviewer/reason and confirm review before approval. Preparing a proposal never changes the directory. Approval preserves original evidence and revision history, rejects stale/duplicate writes, and retains synthetic labels. It does not infer complete funding, numeric language scores or applicant eligibility from prose.

Reproducible offline agent evaluation (no model/source network calls):

```bash
cd backend
.venv/bin/python -m atlas.research.evaluate --output ../docs/evaluation-results.json
.venv/bin/python -m atlas.research.benchmark --output ../docs/benchmark-results.json
```

## Import contract

See [the JSON example](docs/import-example.json) and the [data contract](docs/architecture.md). A minimal real record can contain no claims at all:

```json
{
  "external_id": "my-research-001",
  "title": "A program title transcribed from its official source",
  "institution": "The institution named by that source",
  "country": "The published destination",
  "category": "masters",
  "summary": "My source-based research notes; no funding claims established yet.",
  "synthetic": false,
  "subjects": [],
  "sources": [],
  "facts": {}
}
```

Do not mistake this template for an actual opportunity. Unknown facts are filled with `value: null, state: "unknown"`. Known values start `unverified`. A `verified` (UI: reviewed with evidence) fact requires an internal source ID and supporting excerpt. Source IDs must resolve within that record. In manual imports, website source URLs use HTTP(S) only; they are stored as citations and **are not fetched**. The separate Research Agent can fetch explicitly scoped sources in configured live mode. The importer asserts whether a source is official; ATLAS does not automatically establish that assertion.

Supported fields cover funding, tuition, stipend, travel, insurance, application fees, proof of funds, return obligations, deadline, language, GPA, nationality, degree, and application URL. Task 3 adds original-text `eligibility_conditions`, `language_requirements` and `scholarship_obligations`; these are distinct from numeric rule fields used in matching. Deadline values use ISO dates; GPA uses 0–4 and IELTS 0–9 without automatic conversions. Funding codes are `tuition_and_stipend`, `tuition_only`, `partial`, and `none`. Financial obligations use `yes` / `no`. Every omitted field remains unknown. Other language tests, country-specific grading scales, and complex conditional rules need manual research.

## Checks

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy atlas

cd ../frontend
npm run check
npm run format:check
npm test
npm run build
npm run test:e2e
```

Browser tests start **their own** API on 8001 and Vite on 5174, use a fresh temporary SQLite database, and leave your development data untouched. No already-running dev servers are required. They cover live search/filtering, comparison, source correction/history, profile/matching, application persistence, imports, and mobile overflow. Screenshots/traces are written under ignored `frontend/test-results/` on failure. Accessibility checks use axe against the main screens, alongside native controls, focus states, an accessible modal, reduced-motion support, and a skip link. Automated checks do not replace assistive-technology user testing.

The browser config uses `/usr/bin/chromium` when available. Otherwise install Playwright Chromium:

```bash
cd frontend
PLAYWRIGHT_BROWSERS_PATH=/tmp/atlas-playwright npx playwright install chromium
npm run test:e2e
```

Set `CHROMIUM_EXECUTABLE_PATH` for another installed Chromium. Browser downloads may require allowing `cdn.playwright.dev` and the download redirect destinations in your environment. The provided cloud instance has system Chromium, so a download is unnecessary. The default browser cache path is `/tmp/atlas-playwright`; reinstall if your machine clears `/tmp`.

CI is defined in `.github/workflows/checks.yml`. See [verification notes](docs/verification.md) for observed results from this implementation, including limitations.

## Architecture and deliberate scope

- **FastAPI + Pydantic**: explicit typed validation, structured errors, OpenAPI.
- **SQLAlchemy + Alembic + SQLite**: persistent research, append-only correction history, profiles, and applications. Indexed identity/destination/category columns surround a versioned JSON evidence document. A PostgreSQL migration path is documented, but a PostgreSQL runtime has not been validated.
- **React + TypeScript + Vite + Tailwind CSS**: responsive editorial interface with native controls, semantic headings, and an API proxy. Plain CSS defines the design system alongside Tailwind's build integration; no external fonts or image services are needed.
- **Research engine**: one conditional LangGraph with typed model planning, extraction and tool selection; independent network/verification/budget controls; SQL evidence ledger and deterministic report synthesis. The real OpenAI-compatible provider is disabled by default, and live semantic behavior remains unverified. Third-party APIs may have separate costs.
- **Manual extraction service**: the original deterministic PDF/text import workflow remains available without a model.
- **Matching service**: deterministic rules and visible explanations. Source content never becomes executable instructions.

See [architecture and trust boundaries](docs/architecture.md), [PLAN.md](PLAN.md), and [AGENTS.md](AGENTS.md).

This release is a **single-user, loopback-only development application**, with no authentication, multi-user isolation, scheduled jobs, or hosted deployment. It is intended for small personal libraries; directory views show up to 100 records and some filters scan loaded database records. The API supports limit/offset pagination. Original PDFs from manual import are not retained; hashes and extracted excerpts are. The Research Agent separately retains versioned raw/normalized source snapshots. Reopen the original document when verifying. Scanned PDFs need OCR, which is not included.

Next milestone: run approved models against a legally usable, independently annotated official-document corpus; measure semantic/citation/scope errors and repeated A/B/C performance before claiming live-model quality. Then improve section/condition interpretation, source diffs and durable idempotent jobs. Authentication and parser isolation are prerequisites for public hosting. Fellowship, hackathon, and job categories exist in the data model; specialized ingestion and evaluation remain future work.

## Contributing and license

Contributions are welcome; start with [CONTRIBUTING.md](CONTRIBUTING.md). Code and synthetic fixtures are MIT licensed. Any future imported third-party content remains subject to its source terms.
