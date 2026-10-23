# Contributing to ATLAS

Run the setup and validation commands in README.md before proposing a change. Add tests for observable behavior and preserve the separation between HTTP orchestration, typed validation, storage, extraction, matching, and UI.

For new extraction rules, include ambiguous, missing, malformed, and adversarial examples. Keep facts unknown unless evidence supports a candidate. Never add invented real opportunities or fabricated official citations to fixtures. Synthetic fixtures must remain explicitly labeled in data and UI.

Create Alembic migrations for database changes. Keep dependency locks updated using uv/npm. Do not commit local databases, original private documents, credentials, screenshots containing personal data, or generated build output. Discuss schema/ranking changes in terms of explainable user behavior and uncertainty, not admission predictions.
