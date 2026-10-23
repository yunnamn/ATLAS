# Task 3 measured results

Executed on October 23, 2026 in the prepared Linux environment. These are tiny **synthetic engineering controls**, not real-model or real-document accuracy results. No actual model requests were made. Raw outputs, hashes, prediction spans, decision traces, usage availability and measured latencies are in [benchmark-results.json](benchmark-results.json).

## A/B/C controls

Each approach ran the three fictional Lumen scenarios. A sees one supplied source; B receives both relevant documents in a fixed curated list; C follows the discovered link through the actual graph. The extractor in these controls is deterministic DemoProvider. The same screening/report code is shared.

| Approach | Correct / reference claims | Report citation correctness | Fixture provider calls | Tool calls | Total local seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| A: supplied document | 27 / 35 | 100% | 3 | 3 | 0.2394 |
| B: fixed retrieval | 35 / 35 | 100% | 6 | 6 | 0.2258 |
| C: ATLAS graph | 35 / 35 | 100% | 18 | 6 | 0.2306 |

B and C each recovered 35/35 reference claims; A recovered 27/35 (77.1%). All emitted control claims matched their reference tuples, so the measured report unsupported-claim rate is 0% for all three. This is expected from a labeled deterministic extractor and does not demonstrate hallucination resistance of an LLM. Raw candidate precision/recall is also recorded separately.

B and C detected both labeled conflicting fields in the conflict scenario and retained the missing proof-of-funds field in the insufficient scenario. A missed the two conflicts and the second-source financial information. A also marked proof of funds unknown in the two scenarios where the handbook supplies it. All nine workflows completed; substantive task success was 1/3 for A and 3/3 for B and C against these author-written controls. Partial reports in the conflict/insufficient cases are correct outcomes, not failures hidden as successes.

**No agent accuracy advantage over fixed retrieval was measured.** C used three times as many fixture-provider calls as B. Its visible advantage here is exercising evidence-driven link discovery and plan revision from one seed; B was already supplied both relevant documents. Single-run subsecond local latencies include SQLite and are not a reliable ranking of model or network performance.

Actual model calls and billed model cost: zero. Model input/output token usage: null, because fixtures do not report real usage. There is no authentic corpus/model score table: those prerequisites are missing.

## Semantic and reliability controls

- 18/18 engineer-authored adversarial semantic controls matched expected labels. These are not independent human entailment judgments.
- Tests cover hidden negation, omitted conditions/maxima, wrong financial predicates, applicant restrictions, missing/outdated scope, fabricated/ambiguous quotations, instruction-like evidence, labeled cross-program/intake splicing, scope/version differences, duplicate work and expired-date advisories.
- Provider regressions verify actual OpenAI-compatible HTTP payloads with controlled responses, malformed-schema retries, usage retention for invalid outputs, pre-network input budgets and truncated outputs. No real model quality is inferred.
- Approval tests cover no write before consent, selected-field-only saves, evidence/history preservation, stale revisions, duplicate identities, cross-run access and synthetic-to-real guards. Browser tests cover desktop/mobile approval and citation dialogs with axe.

## Baseline and final checks

- Baseline: 105 backend tests, 10 frontend unit tests, 16 browser/accessibility tests; frontend type/lint/build passed.
- Final backend: **153 tests passed**; Ruff lint/format and mypy passed (31 application files).
- Final frontend: **10 unit tests and 18 browser/accessibility tests passed**; TypeScript, ESLint, Prettier and production build passed.
- Setup script repeated successfully with locked dependencies; existing six demo IDs skipped. Alembic head is 0003 and schema drift check passed.
- Every original row/column in 14 existing tables was compared with the pre-Task 3 SQLite backup and preserved. Tests also upgrade a Task 2 database containing source bytes/claims without altering its old columns.

## Authentic evaluation remains blocked

The approved single-page Erasmus Mundus capture failed at public DNS resolution before source bytes were retrieved. [real-source-capture.json](real-source-capture.json) preserves the failure. The runtime has restricted egress and no approved model endpoint; the pinning/robots transport was not bypassed. There is no independently reviewed authentic reference set. Real semantic accuracy, model tool-choice utility, real-site/PDF retrieval, provider costs, model latency and failure-recovery time remain unmeasured.

[REAL_WORLD_EVALUATION.md](REAL_WORLD_EVALUATION.md) describes corpus provenance, annotation/reconciliation rules, withheld metrics, reproduction commands, approved model setup and Task 4 priorities. A general Erasmus overview also cannot establish program-specific awards; do not turn missing program/intake context into manufactured scholarship facts.
