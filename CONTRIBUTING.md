# Contributing to ATLAS

Run the setup and validation commands in README.md before proposing a change. Add tests for observable behavior and preserve the separation between HTTP orchestration, typed validation, storage, extraction, matching, and UI.

For new extraction rules, include ambiguous, missing, malformed, and adversarial examples. Keep facts unknown unless evidence supports a candidate. Never add invented real opportunities or fabricated official citations to fixtures. Synthetic fixtures must remain explicitly labeled in data and UI.

Create Alembic migrations for database changes. Keep dependency locks updated using uv/npm. Do not commit local databases, original private documents, credentials, screenshots containing personal data, or generated build output. Discuss schema/ranking changes in terms of explainable user behavior and uncertainty, not admission predictions.

## Research and data safety

- Keep the local demo and external-model research paths distinct. Demo results are deterministic fixtures, not measured LLM accuracy.
- Never promote a researched claim into an opportunity record without explicit human review of its source, scope, and revision.
- Treat retrieved text as untrusted data. Use domain-scoped, public-address-pinned HTTP transport with redirect, robots, size, timeout, and request-budget checks; do not bypass network policies when a fetch fails.
- Require explicit opt-in before any paid model or live source request. Do not log provider credentials, raw authentication headers, or private model reasoning.
- Document measured test results separately from model evaluations and clearly identify unavailable data or unverified behavior.

## Development workflow

Work on a feature branch, keep changes focused, and open a pull request with a concise description of behavior and verification. Use the commands in the README for backend linting, type checks, unit tests, frontend checks, and browser tests. Avoid changing dependency lockfiles without the relevant package manager.
