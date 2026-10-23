# Verification record

Observed in the prepared Linux cloud environment on October 23, 2026, with Python 3.12.14, Node 24.19.0, npm 11.9.0, and system Chromium. These results describe this implementation and current instance, not a published snapshot or a validated deployment.

| Check | Observed result |
| --- | --- |
| `./scripts/setup.sh` after initial installation | Passed; frozen uv/npm dependencies installed; migrations applied; all six existing demo IDs skipped without changes |
| `./scripts/dev.sh` | Passed; FastAPI and Vite started on loopback ports 8000/5173; termination cleaned up the services; restarting retained database records |
| Backend `pytest -q` | **31 passed**, no failures/skips; one upstream Starlette/httpx TestClient deprecation warning |
| Backend Ruff lint and format checks | Passed |
| Backend mypy | Passed; 10 application source files checked |
| Alembic `check` | Passed; no model/schema drift |
| Frontend `npm run check` | TypeScript and ESLint passed |
| Frontend `npm run format:check` | Prettier passed |
| Frontend `npm test` | **8 passed** across 2 files |
| Frontend `npm run build` | Passed; production assets generated locally |
| Frontend `npm run test:e2e` | **11 passed** with Chromium; no skipped tests |
| Internal live API and Vite proxy requests | Passed; health responds and the proxied directory returns the expected filtered synthetic record |
| Bash syntax and Git whitespace checks | Passed |

## Behaviors exercised

Backend tests cover record creation/retrieval, duplicate identities, unknown-field normalization, searches and combined filters, pagination, atomic batch validation, repeatable imports that preserve edits, provenance requirements, invalid dates/numeric bounds/unsafe URL schemes, stale revision rejection, before/after history, saved profiles, preference scoring versus academic requirements, provisional rules, unparseable eligibility prose, prior-degree uncertainty, risk flags, application stages/notes/missing requirements, and extra categories.

Fresh-file SQLite tests migrate from empty storage, insert records, dispose/reopen the database, rerun upgrades without losing records, verify repeatable imports, downgrade, and upgrade again. PDF tests exercise a real text PDF, malformed input, excessive file size, encryption, and a PDF without text. Extraction tests ensure source instructions do not affect parsing and ambiguous/invalid candidates are not saved or guessed.

Frontend unit tests cover API errors and uploads, aborting stale query results, explicit unknown presentation, date-only deadlines, synthetic labels, detail links, shortlist actions, and escaped untrusted text.

Browser tests use a separate temporary database and live backend/frontend on 8001/5174. They verify dashboard data, searches and funding/destination filters, comparison, evidence correction with revision history, profile persistence and compatibility explanations, saved applications after a reload, source-text candidates through reviewed JSON import, mobile navigation/profile access, and viewport overflow at 390 pixels. Axe checks pass for all six principal screens, the native import modal, and an expanded evidence-review form. Initial contrast failures were fixed before the final run. Automated accessibility testing is limited to detectable rules in these states and does not establish full conformance or replace manual screen-reader testing.

## Environment and limitations

- The initial Playwright browser download received an environment policy 403 from `cdn.playwright.dev`. Using already-installed `/usr/bin/chromium` resolved browser testing without changing network policy or bypassing verification. The config detects that executable automatically.
- No real opportunity information was researched or verified. All bundled data/citations are synthetic. No paid/model API requests, arbitrary URL downloads, crawling, external messages, deployment, or publication were performed.
- Official source ownership and excerpt truth are not machine-authenticated. Review is a local human assertion and the reviewer name is unauthenticated.
- Original PDFs are not retained. Extraction supports bounded text-based PDFs on Unix, not OCR or arbitrary document prose.
- This is a small-library, single-user local MVP. PostgreSQL, multi-user access, authentication, public hosting, production document isolation, job scheduling, URL ingestion, remote extraction adapters, and fresh-task snapshot restoration have not been validated.
- The GitHub Actions workflow is written but has not been executed remotely. Local checks use the same commands.
- Cloud `install_script` and `start_skill` were saved to a configuration draft. Saving does not execute, apply, or publish them. Review and save the draft in environment settings, then publish the environment to retain the prepared filesystem for future tasks.
