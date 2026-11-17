# Development roadmap

ATLAS is a local, single-user application for evidence-grounded opportunity research. The opportunity directory, application tracker, and research workspace are implemented; their current operating boundaries are described in the [README](../README.md).

## Implemented

- FastAPI, Pydantic, SQLAlchemy, Alembic, and SQLite backend with an opportunity directory, source evidence, revision history, profile checks, and application tracking.
- React/TypeScript frontend with search, comparison, import, source review, research reports, and explicit approval of proposed changes.
- Conditional LangGraph research workflow, configurable OpenAI-compatible provider, bounded source retrieval, persisted evidence, and conservative verification.
- Synthetic offline evaluation, browser/accessibility checks, backend and frontend tests, and GitHub Actions CI.

## Research and engineering priorities

1. **Authentic evaluation:** Assemble a legally usable, independently annotated corpus of official opportunity documents. Run live-model experiments with recorded model versions, settings, source hashes, citation correctness, uncertainty, and error analysis. Existing synthetic results must not be represented as real-model accuracy.
2. **Evidence quality:** Improve section-level context, conditional eligibility, multilingual understanding, and source-version comparison using independently evaluated error cases.
3. **Reliability:** Add a durable, idempotent task queue and deliberate recovery from interrupted research runs. The current in-process worker does not resume work automatically.
4. **Deployment readiness:** Add authentication, multi-user isolation, production-grade document parsing boundaries, backup and migration practices, and observability before public hosting.
5. **Opportunity coverage:** Expand beyond funded master's programs only when ingestion, evaluation, and review rules are specific enough for each new category.

See [agent architecture](AGENT_ARCHITECTURE.md), [research evaluation methodology](REAL_WORLD_EVALUATION.md), [evaluation results](RESEARCH_EVALUATION_RESULTS.md), and the [threat model](THREAT_MODEL.md) for detailed implementation constraints.
