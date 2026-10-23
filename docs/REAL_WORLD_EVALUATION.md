# Task 3: evidence quality, experiments and human approval

## What this milestone establishes

Task 2's single LangGraph and real OpenAI-compatible integration are retained. Task 3 adds evidence sufficiency, scoped comparisons, conservative semantic screening, duplicate-work controls, reproducible comparison infrastructure and human-approved knowledge integration.

**No actual LLM was available or used.** The user's offline preference remains in effect. No independently reviewed authentic reference corpus was supplied. The one official Erasmus Mundus page capture attempted on October 23, 2026 failed with `dns_failed`; [real-source-capture.json](real-source-capture.json) records that actual result. No source bytes were obtained and no alternative transport bypass was attempted. Do not describe this release as experimentally validated real-world autonomy.

The core app, real provider protocol, graph, persistence, screening, comparison runner and review workflow execute without paid services. Real-model extraction, planning, discovery quality and genuine source connectivity still require verification.

## Actual adaptive behavior and limits

- PLAN still decomposes objectives into typed questions. In live mode, the model selects fetch/search/re-extract/stop and may revise its plan; code rejects revisions that drop required fields. The controlled HTTP integration test drives these real request/response mechanics, not a real model.
- DECIDE receives question/field sufficiency, unresolved support failures, scope/version differences, past-deadline advisories, pending sources with priority reasons and remaining extraction passes. Source priority uses caller-supplied seeds, relevance vocabulary and intake indicators; it does not authenticate authority or currentness.
- Same normalized search queries and identical extraction focus/windows are rejected. A document remains limited to two extraction passes. Identical raw bytes at another URL are retained as a source use but do not trigger another extraction or false corroboration.
- Decision observations are packed to approximately 24,000 serialized characters with original collection totals and a truncation flag. Validation retains the complete ledger. Per-request input is still capped at 55,000 characters; complex oversized objectives/plans fail explicitly rather than bypassing limits.
- A cumulative serialized input budget defaults to 240,000 bytes (hard maximum 480,000), alongside existing request, network, tool, time and reserved output-token limits. Input bytes are not a tokenizer-specific token or cost guarantee. Invalid responses still count toward request/input/output reservations; provider-reported usage is recorded before schema validation. Truncated completions fail explicitly.
- Tools available: scoped HTTP(S) HTML/text-PDF retrieval, saved document windows and an optional administrator-configured SearxNG JSON service. No search service, model weights, OCR, login browser, CAPTCHA solver, shell, application submission, email or purchasing tool is bundled.
- Sufficiency is field coverage within observed scopes. It does not prove arbitrary prose completion criteria, discover every program mentioned in an objective, or establish admissions eligibility. Missing and conflicting fields keep reports partial. Stopping without enough evidence never creates an inferred answer.

## Support assessment contract

Migration `0003` adds a JSON assessment to each new claim, independently of exact evidence IDs. Legacy claims get `{}`; frozen Task 2 reports are preserved.

| Label | Meaning of this implementation |
| --- | --- |
| Fully supported | Exact value/support/scope spans and the bounded English field/context checks passed |
| Partially supported | A recognized condition, maximum or applicant restriction was omitted |
| Unsupported | Exact citation/value fails, or the passage concerns a different/unestablished field |
| Contradicted | A recognized omitted negation can reverse the proposed meaning |
| Insufficient evidence | Scope/intake is missing or inapplicable, context exceeds the window, or the proposed evidence is instruction-like |

The record includes method, label, inspected passage, reason, resolution, span and `independent_ground_truth: false`. The UI displays the rule screen separately from source support. A valid quotation with failed semantic checks keeps its evidence IDs but stays unverified and outside report findings and proposals.

Checks inspect the complete containing source line, selected adjacent conditional lines, a field predicate in the value's sentence, explicit applicant restrictions, requested intake, and labeled program/intake boundaries. These catch concrete misleading-fragment and cross-program splicing controls. **They do not establish general semantic entailment.** Unlabeled tables, translated prose, long-range conditions, sarcasm, complex legal rules or misleading statements can evade heuristics. An unrelated nearby negation can also cause a false rejection. Human review remains essential; there is no LLM judge presented as ground truth.

Award track, applicant group and source version are optional explicit scope dimensions and must occur in the exact scope passage when asserted. Different intakes/tracks/groups and changed same-URL source versions are shown as contextual differences, not automatically as true contradictions. Missing dimensions remain unresolved. Canonical conflict detection remains deliberately narrow: tuition coverage, proof-of-funds requirements, ISO deadlines and same-currency numeric fees. It does not solve arbitrary natural-language contradiction detection or independently establish source priority.

## Experimental design

`atlas.research.benchmark` evaluates the same extractor, mechanical/semantic screen and deterministic reporting boundary under three schedules:

1. **A_direct:** one supplied frozen document, one extraction; no model planning or replanning.
2. **B_fixed_retrieval:** a predeclared list of corpus documents, extraction over each; no adaptive decisions, search or link following. In the tiny controls this curated list contains both relevant documents. This is a favorable fixed-retrieval baseline, not a measured search engine.
3. **C_adaptive:** the actual conditional graph starts from the supplied document, follows discovered links and receives new observations before deciding/revising/stopping. Real runs use the configured model for those choices; synthetic controls use DemoProvider.

Authentic A/B/C experiments replay identical frozen bytes, so availability changes do not confound model behavior. They evaluate research over the supplied corpus, not live web discovery. URLs outside that corpus fail explicitly. A separate opt-in live smoke tests actual transport/workflow. Run multiple trials/models and larger corpora before making statistical or comparative quality claims.

The runner retains corpus/byte hashes, source metadata, configuration/software versions, prediction values/scopes/support spans, observable decision traces, failure analysis, latency, tool/provider counts and retained partial findings. Raw candidate extraction precision/recall is separate from screened-report precision/recall. Citation correctness additionally compares the annotated support quote; exact-span validity alone is not entailment.

Reference labels must cover the evaluated ontology exhaustively: an unreferenced tuple is a reference mismatch, not independent proof of a hallucination. Multiple valid passages may require additional accepted reference spans in a larger corpus.

Unknown/conflict metrics compare field sets; they do not yet score applicant-specific semantic relations. Completeness measures the fraction of reference claim tuples recovered. Task success requires reference claims, unknowns and conflicts to match. No-claim precision or no-positive conflict recall is null. Failure injection is covered by regression tests, not claimed as a timed recovery benchmark. Single-run wall latency includes local SQLite and is not a provider performance estimate.

Token usage is provider-reported and remains null in fixtures. Dollar estimates require explicit finite input/output USD prices per million tokens and complete reported usage for every actual request. Failures or missing metadata leave estimates null. No model calls means zero model cost for the controls; package installation and local compute are not assigned invented dollar costs.

### Reference corpus and annotation rules

Use [benchmark-manifest.example.json](benchmark-manifest.example.json) as an **unannotated template**, not an authentic captured corpus. Its zero hash and replacement paths/dates are intentional placeholders; execution fails until real bytes and provenance are supplied.

For each source record: retain the official URL, retrieved timestamp, immutable byte SHA-256, MIME type, relative snapshot path, owner assertion and reuse note. Public accessibility does not itself authorize redistribution. Raw third-party snapshots should remain under ignored `backend/data/corpus`; review source terms and privacy before publishing excerpts or experiment outputs. No human annotations or authentic document contents have been fabricated in this repository.

Annotate before inspecting predictions:

- Declare the objective and question fields without using model output as reference truth.
- Label exact field/value phrases with program, intake, track, applicant group and source-version scope; preserve negations, limits, currencies, conditional awards and page/section context.
- Record exact support quotes from the frozen normalized text. Explicitly distinguish not stated from false, inapplicable historical data and contradictory same-scope evidence.
- List required fields with no adequate evidence and conflicting fields. Explain ambiguity and exclusions in `annotation_notes`; do not force a guessed answer.
- Have two named independent reviewers label the same snapshot, reconcile disagreements, record their identities and agreement process, then declare `independently_reviewed`. The schema requires two distinct names; this is a caller assertion, not identity authentication. A single `author_labeled` authentic corpus may run but its quality scores are withheld.
- Keep a held-out corpus for model/prompt changes. Report inter-annotator agreement and unresolved cases separately; this implementation has no such measured dataset yet.

The bundled synthetic labels are engineer-authored control expectations, not human ground truth. Their results are separate from authentic experiments. Passing them cannot establish LLM research quality.

## Reproduce without model requests

```bash
./scripts/setup.sh
cd backend
.venv/bin/python -m atlas.research.evaluate --output ../docs/evaluation-results.json
.venv/bin/python -m atlas.research.benchmark --output ../docs/benchmark-results.json
```

Actual comparison output and interpretation: [TASK3_RESULTS.md](TASK3_RESULTS.md). The second command performs nine tiny synthetic runs and 18 authored semantic controls, using temporary databases. It does not modify your opportunity library or invoke a model/source service.

One explicit source capture, only in a runtime with approved public DNS/direct egress:

```bash
cd backend
.venv/bin/python -m atlas.research.benchmark \
  --capture-url 'https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/erasmus-mundus-joint-masters' \
  --capture-dir data/corpus --output data/capture-result.json
```

This honors the same robots, scope, pinning, size/type/time and access policy as live research. A blocked capture exits nonzero and records the reason. The current cloud instance failed at DNS; changing to an unpinned/proxy client is not an acceptable fix.

## Connect an approved model

The default remains disabled. Start an already-installed OpenAI-compatible local server separately; ATLAS does not install/download a model or assume hardware availability. From `backend/`, securely set environment variables or a local ignored `.env`:

```dotenv
ATLAS_LLM_ENABLED=true
ATLAS_LLM_BASE_URL=http://127.0.0.1:11434/v1
ATLAS_LLM_MODEL=your-already-installed-model
ATLAS_LLM_JSON_MODE=json_object
```

Replace endpoint/model with your actual approved configuration. `json_schema` is the default for compatible strict providers; use `json_object` for endpoints without strict-schema support. Remote endpoints require HTTPS; loopback HTTP is supported for local servers. Put any `ATLAS_LLM_API_KEY` in secure environment settings, never Git/chat. Hosted inference may have separate charges. Restart the single backend process, select Live mode, supply a specific objective/intake and official seed URLs/domains, then explicitly consent to model requests and excerpt transmission. Optional search requires a configured `ATLAS_SEARCH_BASE_URL`; no search is silently enabled.

For authentic frozen-corpus comparisons, after capture and independent annotation:

```bash
cd backend
.venv/bin/python -m atlas.research.benchmark \
  --manifest data/corpus/manifest.json --case your-reviewed-case \
  --allow-model-requests --output data/real-experiment.json
```

This flag authorizes all three approaches for that one case, each with its recorded hard limits (up to 24 provider requests and 24,000 reserved output tokens per approach). Optional `--input-usd-per-million` / `--output-usd-per-million` record your provider's actual prices; prices do not create a spending guarantee. Without independent labels, authentic quality metrics are null. The CLI never activates a default paid provider or silently substitutes fixtures for a live failure.

## Human-reviewed integration

After a final or partial report, open **Review changes**. Select scope and either enter a new record's identity or choose an existing target/revision. Preparing a proposal only persists a review artifact. Inspect before/after values, exact support/scope quotes, hashes and saved sources, select individual fields, enter reviewer/reason and explicitly confirm source review before approving.

Only conflict-free findings with a fully supported rule assessment can be proposed. Multiple distinct values for one target field are blocked pending reconciliation. Approval revalidates original evidence and both revisions and commits opportunity/history/proposal state atomically. Retry, duplicate identity or stale writes cannot create a second record or silently overwrite a correction. Synthetic evidence cannot update a real opportunity; new demo-derived records retain their synthetic label.

Institution/program/destination identity is explicitly supplied by the reviewer. Funding facts map conservatively to tuition/stipend, ISO deadlines, fees and explicit proof-of-funds rules. Original eligibility, language and scholarship-obligation wording now has dedicated fact keys. No aggregate fully-funded status, IELTS score, nationality list or return-obligation boolean is guessed from complex prose. Unselected/unmapped facts remain unknown. Source authority remains unasserted unless separately reviewed. `verified` means a local declared human review, not authenticated truth or reviewer identity.

## Remaining Task 4 priorities

1. Obtain an approved model/runtime and several legally usable official HTML/PDF snapshots. Build a blinded, independently annotated corpus and execute repeated A/B/C trials; measure semantic entailment, scope, citation attribution, conflicts, coverage and real cost/failure behavior.
2. Improve document-section/applicant-condition interpretation against held-out errors, compare an optional independent verifier with human labels, and calibrate uncertainty. Extend beyond English heuristics without treating an LLM judge as ground truth.
3. Validate a trusted pinned source gateway or direct public egress in the intended host, then add source diffs. Add durable idempotent jobs, authenticated reviewers and OS-isolated parsing before multi-user/public deployment.
