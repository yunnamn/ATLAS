import {
  ArrowRight,
  BookOpenText,
  Bot,
  Check,
  ChevronDown,
  CircleStop,
  FileSearch,
  FlaskConical,
  Play,
  RotateCw,
  ShieldCheck,
} from 'lucide-react'
import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, formatDate, useResource } from '../api'
import { ErrorBox, Loading } from '../components/ui'
import { SavedSource } from '../components/ResearchSource'
import { ResearchReview } from '../components/ResearchReview'
import { useWorkspace } from '../components/workspace'
import { DEMO_OBJECTIVE, researchLabels, terminal, useResearchRun } from '../research'
import type {
  Capabilities,
  ResearchClaim,
  ResearchDocument,
  ResearchEvidence,
  ResearchReport,
  ResearchRun,
  ResearchSnippet,
} from '../research'

export function ResearchState({ state }: { state: string }) {
  const names: Record<string, string> = {
    source_supported: 'Source-supported',
    corroborated: 'Corroborated · declared groups',
    contradictory: 'Conflicting',
    unverified: 'Unverified',
    unknown: 'Unknown',
    fully_supported: 'Fully supported · rule screen',
    partially_supported: 'Partially supported',
    unsupported: 'Unsupported',
    contradicted: 'Contradicted',
    insufficient_evidence: 'Insufficient evidence',
  }
  return (
    <span className={`research-badge research-${state}`}>
      <span className="status-dot" />
      {names[state] ?? state}
    </span>
  )
}

function EvidenceView({ runId, evidence }: { runId: string; evidence: ResearchEvidence }) {
  const [inspecting, setInspecting] = useState<{
    document: ResearchDocument
    snippet?: ResearchSnippet
  } | null>(null)
  function inspect(id: string | null) {
    const snippet = evidence.snippets.find((s) => s.id === id)
    const document = evidence.documents.find((d) => d.id === snippet?.document_id)
    if (document && snippet) setInspecting({ document, snippet })
  }
  return (
    <div className="research-evidence">
      <div className="section-heading">
        <h2>Claims & evidence</h2>
        <span className="muted">{evidence.claims.length} extracted candidates</span>
      </div>
      <p className="muted">
        Exact citations and a conservative English support screen are separate checks. These checks
        do not establish truth, official ownership, or complete eligibility.
      </p>
      {evidence.claims.length > 0 ? (
        <div className="research-claim-list">
          {evidence.claims.map((claim: ResearchClaim) => (
            <article key={claim.id} className="research-claim">
              <div>
                <strong>{researchLabels[claim.field] ?? claim.field}</strong>
                <ResearchState state={claim.state} />
              </div>
              <p>{claim.value}</p>
              <small>
                {claim.scope.program} · {claim.scope.intake_year ?? 'Intake unknown'}
                {claim.scope.award_track && ` · ${claim.scope.award_track}`}
                {claim.scope.applicant_group && ` · ${claim.scope.applicant_group}`}
              </small>
              <p>
                <ResearchState
                  state={claim.semantic_assessment?.label ?? 'insufficient_evidence'}
                />
              </p>
              {claim.state === 'unverified' && (
                <p className="muted">
                  Excluded from report findings. A real quote can still fail to support the proposed
                  meaning.
                </p>
              )}
              <div className="research-citation-row">
                {claim.evidence_id ? (
                  <>
                    <button className="text-link" onClick={() => inspect(claim.evidence_id)}>
                      <BookOpenText size={14} />
                      Inspect supporting citation
                    </button>
                    <button className="text-link" onClick={() => inspect(claim.scope_evidence_id)}>
                      Inspect scope
                    </button>
                  </>
                ) : (
                  <span className="muted">
                    No validated citation. Excluded from report findings.
                  </span>
                )}
              </div>
              <details>
                <summary>Verification note</summary>
                <p>{claim.verification_note}</p>
                {claim.semantic_assessment?.passage && (
                  <blockquote>{claim.semantic_assessment.passage}</blockquote>
                )}
                {claim.semantic_assessment?.resolution && (
                  <p>{claim.semantic_assessment.resolution}</p>
                )}
              </details>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">
          No claims extracted yet. Empty evidence is never filled with a generated answer.
        </p>
      )}
      {evidence.unknowns.length > 0 && (
        <section className="research-unknowns">
          <h3>Still unknown</h3>
          {evidence.unknowns.map((u, i) => (
            <p key={i}>
              <ResearchState state="unknown" />
              {researchLabels[u.field] ?? u.field}
              {u.scope && <small>{u.scope.program}</small>}
            </p>
          ))}
        </section>
      )}
      {evidence.contradictions.length > 0 && (
        <section className="research-conflicts">
          <h3>Conflicting source statements</h3>
          {evidence.contradictions.map((c) => (
            <p key={c.id}>{c.summary}</p>
          ))}
          <small>
            Both claims and their citations remain visible. ATLAS does not choose a winner
            automatically.
          </small>
        </section>
      )}
      <section className="research-source-list">
        <h3>Source documents</h3>
        {evidence.documents.map((d) => (
          <div key={d.id}>
            <FileSearch size={17} />
            <span>
              <strong>{d.title}</strong>
              <small>{d.url}</small>
              <small>
                Last checked {formatDate(d.last_checked_at)}
                {d.synthetic ? ' · synthetic fixture' : ''}
              </small>
            </span>
            <button
              className="btn secondary btn-small"
              onClick={() => setInspecting({ document: d })}
            >
              Inspect saved text
            </button>
          </div>
        ))}
        {evidence.sources
          .filter((s) => !s.document_id)
          .map((s) => (
            <div key={s.id}>
              <span>
                <strong>{s.status.replaceAll('_', ' ')}</strong>
                <small>{s.url}</small>
                <small>{s.message}</small>
              </span>
            </div>
          ))}
        {evidence.sources.some((s) => s.cache_hit) && (
          <p className="muted">
            Cached evidence reused. Its last actual verification date is shown; reuse does not mean
            the source was refreshed.
          </p>
        )}
      </section>
      {inspecting && (
        <SavedSource
          key={`${inspecting.document.id}-${inspecting.snippet?.id}`}
          runId={runId}
          document={inspecting.document}
          excerpt={inspecting.snippet}
          close={() => setInspecting(null)}
        />
      )}
    </div>
  )
}

function ReportView({
  report,
  evidence,
  showEvidence,
}: {
  report: ResearchReport
  evidence?: ResearchEvidence
  showEvidence: () => void
}) {
  return (
    <section className="research-report">
      <div className="section-heading">
        <div>
          <div className="eyebrow">EVIDENCE-LED SYNTHESIS</div>
          <h2>{report.outcome === 'complete' ? 'Research report' : 'Partial research report'}</h2>
        </div>
        <ResearchState state={report.outcome} />
      </div>
      <p className="report-summary">{report.executive_summary}</p>
      {(report.temporal_warnings?.length ?? 0) > 0 && (
        <section>
          <h3>Dates requiring attention</h3>
          {report.temporal_warnings?.map((w) => (
            <p key={w.claim_id}>
              {w.value}: {w.warning} Checked against {w.as_of_date}.
            </p>
          ))}
        </section>
      )}
      {report.question_assessments && (
        <section className="research-sufficiency">
          <h3>Evidence sufficiency by question</h3>
          <p className="muted">
            Field coverage is checked. Natural-language completion criteria still need human review.
          </p>
          {report.question_assessments.map((q, i) => (
            <details key={i}>
              <summary>
                {q.question} · {q.status.replaceAll('_', ' ')}
              </summary>
              {q.fields.map((f) => (
                <p key={f.field}>
                  {researchLabels[f.field] ?? f.field}: {f.status.replaceAll('_', ' ')}.{' '}
                  {f.resolution}
                </p>
              ))}
            </details>
          ))}
        </section>
      )}
      {(report.context_differences?.length ?? 0) > 0 && (
        <section>
          <h3>Differences in applicability or source version</h3>
          {report.context_differences?.map((d, i) => (
            <p key={i}>
              {researchLabels[d.field] ?? d.field}: {d.relation.replaceAll('_', ' ')}.{' '}
              {d.resolution}
            </p>
          ))}
        </section>
      )}
      {report.synthetic && (
        <p className="research-demo-note">
          <FlaskConical size={17} />
          Deterministic fixture result. No actual LLM or external research was performed.
        </p>
      )}
      <h3>Investigated programs</h3>
      {report.investigated_opportunities.length ? (
        report.investigated_opportunities.map((o, i) => (
          <p className="report-program" key={i}>
            {o.program} <span>{o.intake_year ?? 'Intake unknown'}</span>
          </p>
        ))
      ) : (
        <p className="muted">No program established by source evidence.</p>
      )}
      <h3>Source-backed findings</h3>
      <div className="report-findings">
        {report.findings.map((f) => (
          <div key={f.claim_id}>
            <span>{researchLabels[f.field] ?? f.field}</span>
            <div>
              <strong>{f.value}</strong>
              <ResearchState state={f.state} />
              <button className="text-link" onClick={showEvidence}>
                Inspect citation <ArrowRight size={12} />
              </button>
            </div>
          </div>
        ))}
        {!report.findings.length && (
          <p className="muted">No source-supported findings are available.</p>
        )}
      </div>
      {evidence && evidence.contradictions.length > 0 && (
        <section className="research-conflicts">
          <h3>Conflicts requiring investigation</h3>
          {evidence.contradictions.map((c) => (
            <p key={c.id}>{c.summary}</p>
          ))}
          <button className="text-link" onClick={showEvidence}>
            Inspect both source statements <ArrowRight size={13} />
          </button>
        </section>
      )}
      <h3>Unanswered questions</h3>
      {report.unanswered_questions.length ? (
        report.unanswered_questions.map((q, i) => (
          <p className="unanswered-line" key={i}>
            <ResearchState state="unknown" />
            <span>
              {researchLabels[q.field] ?? q.field} — {q.reason}
            </span>
          </p>
        ))
      ) : (
        <p className="muted">
          No missing fields in the recorded plan. Unmodeled requirements and source accuracy still
          require review.
        </p>
      )}
      {report.recommended_next_investigations.length > 0 && (
        <>
          <h3>Recommended next investigations</h3>
          <ul className="research-next-steps">
            {report.recommended_next_investigations.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </>
      )}
      <details className="report-limitations">
        <summary>
          Run metadata & limitations <ChevronDown size={14} />
        </summary>
        <p>
          Stop reason: {report.run_metadata.stop_reason.replaceAll('_', ' ')} ·{' '}
          {report.run_metadata.plan_revisions} plan revisions
        </p>
        <p>
          Provider path:{' '}
          {report.run_metadata.llm_driven
            ? 'Configured model endpoint'
            : 'Offline deterministic fixture'}
        </p>
        <ul>
          {report.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </details>
    </section>
  )
}

function RunWorkspace({ id, finished }: { id: string; finished: () => void }) {
  const { run, evidence, report, error } = useResearchRun(id, finished)
  const [tab, setTab] = useState<'progress' | 'evidence' | 'report' | 'review'>('progress')
  const [cancelling, setCancelling] = useState(false)
  const { notify } = useWorkspace()
  async function cancel() {
    setCancelling(true)
    try {
      await api(`/research/runs/${id}/cancel`, { method: 'POST' })
      notify('Cancellation requested. The current bounded request may need to finish first.')
    } catch (e) {
      notify((e as Error).message, true)
      setCancelling(false)
    }
  }
  if (!run) return error ? <ErrorBox error={error} /> : <Loading />
  const plan = run.plans.at(-1)
  return (
    <div className="research-run-workspace">
      {error && <ErrorBox error={error} />}
      <section className="panel research-run-heading">
        <div className="section-heading">
          <div>
            <div className="eyebrow">
              {run.mode === 'demo'
                ? 'SYNTHETIC OFFLINE DEMONSTRATION'
                : 'CONFIGURED MODEL RESEARCH'}
            </div>
            <h2>Your investigation</h2>
          </div>
          <ResearchState state={run.status} />
        </div>
        <p className="research-objective">{run.objective}</p>
        <small>
          Run {run.id} · Started {formatDate(run.created_at)}
        </small>
        {run.mode === 'demo' && (
          <p className="research-demo-note">
            <FlaskConical size={16} />
            Uses fictional Lumen sources and deterministic decisions. This does not verify real
            opportunities or live model autonomy.
          </p>
        )}
        <div className="research-run-stats">
          <span>
            <strong>{run.stats.tool_calls ?? 0}</strong> tool calls
          </span>
          <span>
            <strong>{run.stats.documents_examined ?? 0}</strong> documents
          </span>
          <span>
            <strong>{run.stats.iterations ?? 0}</strong> decisions
          </span>
          <span>
            <strong>{run.stats.model_http_requests ?? 0}</strong> real model requests
          </span>
        </div>
        {!terminal(run.status) && (
          <button
            className="btn secondary btn-small"
            disabled={cancelling || run.cancel_requested}
            onClick={cancel}
          >
            <CircleStop size={14} />
            {cancelling || run.cancel_requested ? 'Cancellation requested…' : 'Cancel run'}
          </button>
        )}
        {run.error && (
          <p className="inline-error" role="alert">
            {run.error}
          </p>
        )}
      </section>
      <div className="tabs research-tabs" aria-label="Research views">
        <button className={tab === 'progress' ? 'selected' : ''} onClick={() => setTab('progress')}>
          Plan & activity
        </button>
        <button className={tab === 'evidence' ? 'selected' : ''} onClick={() => setTab('evidence')}>
          Evidence & sources <span>{evidence?.claims.length ?? 0}</span>
        </button>
        <button
          className={tab === 'report' ? 'selected' : ''}
          disabled={!report}
          onClick={() => setTab('report')}
        >
          Report {report && <Check size={13} />}
        </button>
        <button
          className={tab === 'review' ? 'selected' : ''}
          disabled={!report}
          onClick={() => setTab('review')}
        >
          Review changes
        </button>
      </div>
      <section className="panel research-result-panel">
        {tab === 'progress' ? (
          <>
            <div className="section-heading">
              <h2>Research plan</h2>
              {plan && <span className="research-plan-revision">Revision {plan.revision}</span>}
            </div>
            {plan ? (
              <div className="research-plan">
                {plan.content.questions.map((q) => (
                  <div key={q.id}>
                    <span>{q.id.toUpperCase()}</span>
                    <div>
                      <strong>{q.question}</strong>
                      <p>{q.completion_criterion}</p>
                      <div className="tags">
                        {q.fields.map((f) => (
                          <span key={f}>{researchLabels[f] ?? f}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
                <details>
                  <summary>Constraints & completion criteria</summary>
                  <ul>
                    {[...plan.content.constraints, ...plan.content.completion_criteria].map(
                      (c, i) => (
                        <li key={i}>{c}</li>
                      ),
                    )}
                  </ul>
                  {plan.content.search_tasks.length > 0 && (
                    <>
                      <h3>Planned searches</h3>
                      <ul>
                        {plan.content.search_tasks.map((q, i) => (
                          <li key={i}>{q}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </details>
                {run.plans.length > 1 && (
                  <details>
                    <summary>Previous plan revisions</summary>
                    {run.plans.slice(0, -1).map((p) => (
                      <div key={p.revision}>
                        <strong>Revision {p.revision}</strong>
                        <ul>
                          {p.content.questions.map((q) => (
                            <li key={q.id}>{q.question}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            ) : (
              <p className="muted">Waiting for a typed research plan.</p>
            )}
            <div className="section-heading research-activity-heading">
              <h2>Observable activity</h2>
              <span className="muted">{run.steps.length} events</span>
            </div>
            <div className="research-timeline" aria-live="polite" aria-relevant="additions">
              {run.steps.map((s) => (
                <article key={s.id}>
                  <span className={`node-dot node-${s.node.toLowerCase()}`}>
                    {s.sequence.toString().padStart(2, '0')}
                  </span>
                  <div>
                    <strong>{s.node}</strong>
                    <p>{s.summary}</p>
                    {s.data.action ? (
                      <small>
                        Action: {String(s.data.action)}
                        {s.data.plan_revision ? ` · plan revision ${s.data.plan_revision}` : ''}
                      </small>
                    ) : null}
                  </div>
                </article>
              ))}
              {!terminal(run.status) && (
                <div className="research-working">
                  <span className="spinner" />
                  {run.cancel_requested
                    ? 'Waiting for bounded work to stop…'
                    : `${run.state.phase ?? 'Pending'} · investigation in progress`}
                </div>
              )}
            </div>
            {report && (
              <button className="btn primary" onClick={() => setTab('report')}>
                Read {report.outcome === 'partial' ? 'partial ' : ''}report <ArrowRight size={15} />
              </button>
            )}
          </>
        ) : tab === 'evidence' && evidence ? (
          <EvidenceView runId={id} evidence={evidence} />
        ) : tab === 'review' && evidence && report ? (
          <ResearchReview runId={id} evidence={evidence} report={report} />
        ) : tab === 'report' && report ? (
          <ReportView report={report} evidence={evidence} showEvidence={() => setTab('evidence')} />
        ) : (
          <p className="muted">No results available yet.</p>
        )}
      </section>
    </div>
  )
}

export function ResearchAgent() {
  const [params, setParams] = useSearchParams()
  const [historyRevision, setHistoryRevision] = useState(0)
  const [mode, setMode] = useState<'demo' | 'live'>('demo')
  const [objective, setObjective] = useState(DEMO_OBJECTIVE)
  const [seeds, setSeeds] = useState('')
  const [domains, setDomains] = useState('')
  const [scenario, setScenario] = useState('funding_gap')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [budget, setBudget] = useState({
    max_iterations: 6,
    max_documents: 4,
    max_model_requests: 12,
    max_seconds: 120,
    max_output_tokens: 12000,
    max_input_bytes: 240000,
  })
  const capabilities = useResource<Capabilities>('/research/capabilities')
  const history = useResource<ResearchRun[]>('/research/runs', historyRevision)
  const finished = useCallback(() => setHistoryRevision((n) => n + 1), [])
  const selected = params.get('run')
  async function start(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api<{ id: string }>('/research/runs', {
        method: 'POST',
        body: JSON.stringify({
          objective,
          mode,
          demo_scenario: scenario,
          limits: budget,
          allow_model_requests: mode === 'live' && consent,
          ...(mode === 'live'
            ? {
                seed_urls: seeds
                  .split('\n')
                  .map((v) => v.trim())
                  .filter(Boolean),
                allowed_domains: domains
                  .split(',')
                  .map((v) => v.trim())
                  .filter(Boolean),
              }
            : {}),
        }),
      })
      setParams({ run: result.id })
      setHistoryRevision((n) => n + 1)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="page research-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">QUESTION. INVESTIGATE. VERIFY.</div>
          <h1>Research with a clear trail.</h1>
          <p>A bounded research agent, with its plan, decisions, and evidence kept in view.</p>
        </div>
        <span className="research-local-tag">
          <ShieldCheck size={15} />
          Read-only external tools
        </span>
      </div>
      <div className="research-layout">
        <aside className="research-input-column">
          <form className="panel research-input-form" onSubmit={start}>
            <div className="section-heading">
              <h2>Start an investigation</h2>
              <Bot size={21} />
            </div>
            <label>
              Research mode
              <select value={mode} onChange={(e) => setMode(e.target.value as 'demo' | 'live')}>
                <option value="demo">Offline synthetic demo</option>
                <option value="live">Configured LLM research</option>
              </select>
            </label>
            <p className="field-note">
              {mode === 'demo'
                ? 'Runs fixed fictional sources with a deterministic fixture provider. It does not research the web or use a real language model.'
                : capabilities.data?.model_notice}
            </p>
            <label>
              Research objective
              <textarea
                value={objective}
                minLength={20}
                maxLength={4000}
                required
                onChange={(e) => setObjective(e.target.value)}
                rows={6}
              />
            </label>
            {mode === 'demo' ? (
              <label>
                Demonstration scenario
                <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                  <option value="funding_gap">
                    Missing condition → investigate another source
                  </option>
                  <option value="conflict">Conflicting funding & deadline statements</option>
                  <option value="insufficient">Insufficient proof-of-funds evidence</option>
                </select>
              </label>
            ) : (
              <>
                <label>
                  Starting official URLs (one per line)
                  <textarea
                    value={seeds}
                    onChange={(e) => setSeeds(e.target.value)}
                    rows={3}
                    placeholder="https://official-university.example/program"
                  />
                </label>
                <label>
                  Additional approved domains (comma-separated)
                  <input
                    value={domains}
                    onChange={(e) => setDomains(e.target.value)}
                    placeholder="scholarship-organization.example"
                  />
                </label>
                <p className="field-note">
                  Starting URL hosts are included automatically. New links and search results must
                  stay within exact approved domains. Official ownership is your assertion; ATLAS
                  does not authenticate it.
                </p>
                {!capabilities.data?.live_ready && (
                  <div className="research-config-note">
                    <strong>Live provider is not configured.</strong>
                    <p>
                      Set ATLAS_LLM_BASE_URL and ATLAS_LLM_MODEL, and explicitly enable
                      ATLAS_LLM_ENABLED on the backend. Store any key securely as ATLAS_LLM_API_KEY.
                      Local Ollama-compatible endpoints are supported; hosted providers may charge
                      separately.
                    </p>
                  </div>
                )}
                <p className="field-note">
                  Broader search:{' '}
                  {capabilities.data?.search_configured
                    ? 'configured, within approved source scope'
                    : 'not configured; supply starting URLs to investigate'}
                </p>
                <label className="checkbox-panel">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  <span>
                    I authorize requests to the configured model and understand that source excerpts
                    will be sent and separate costs may apply.
                  </span>
                </label>
              </>
            )}
            <details className="research-budget">
              <summary>
                Research limits <ChevronDown size={14} />
              </summary>
              <div className="form-grid">
                {(
                  [
                    { key: 'max_documents', label: 'Documents', max: 8, min: 1 },
                    { key: 'max_iterations', label: 'Decision iterations', max: 12, min: 1 },
                    { key: 'max_model_requests', label: 'Provider requests', max: 24, min: 1 },
                    { key: 'max_seconds', label: 'Elapsed seconds', max: 180, min: 1 },
                    {
                      key: 'max_output_tokens',
                      label: 'Output token reservation',
                      max: 24000,
                      min: 512,
                    },
                    {
                      key: 'max_input_bytes',
                      label: 'Model input size budget (bytes)',
                      max: 480000,
                      min: 1024,
                    },
                  ] as const
                ).map((item) => (
                  <label key={item.key}>
                    {item.label}
                    <input
                      type="number"
                      required
                      min={item.min}
                      max={item.max}
                      value={budget[item.key]}
                      onChange={(e) =>
                        setBudget((b) => ({ ...b, [item.key]: Number(e.target.value) }))
                      }
                    />
                  </label>
                ))}
              </div>
              <p className="field-note">
                Additional hard limits: 10 logical tool calls, 24 network requests, two extraction
                windows per document. Provider retries consume the same request/token budget.
                Offline counters are fixture operations, not model usage.
              </p>
            </details>
            {error && (
              <div className="inline-error" role="alert">
                {error}
              </div>
            )}
            {capabilities.error && <ErrorBox error={capabilities.error} />}
            <button
              className="btn primary"
              disabled={
                busy ||
                capabilities.loading ||
                (mode === 'live' && (!capabilities.data?.live_ready || !consent))
              }
            >
              <Play size={15} />
              {busy ? 'Starting…' : mode === 'demo' ? 'Start offline demo' : 'Start live research'}
            </button>
          </form>
          <section className="panel research-history">
            <div className="section-heading">
              <h2>Recent investigations</h2>
              <button
                className="icon-btn"
                type="button"
                aria-label="Refresh investigations"
                onClick={finished}
              >
                <RotateCw size={15} />
              </button>
            </div>
            {history.error && <ErrorBox error={history.error} />}
            {history.data?.length ? (
              history.data.map((run) => (
                <button
                  key={run.id}
                  className={selected === run.id ? 'selected' : ''}
                  onClick={() => setParams({ run: run.id })}
                >
                  <span>{run.objective}</span>
                  <small>
                    {run.mode === 'demo' ? 'Synthetic demo' : 'Configured model'} · {run.status}
                    {run.outcome ? ` · ${run.outcome}` : ''}
                  </small>
                </button>
              ))
            ) : (
              <p className="muted">Your saved investigations will appear here.</p>
            )}
          </section>
        </aside>
        <div className="research-output-column">
          {selected ? (
            <RunWorkspace key={selected} id={selected} finished={finished} />
          ) : (
            <section className="panel research-welcome">
              <span className="research-welcome-icon">
                <FileSearch size={38} strokeWidth={1.3} />
              </span>
              <div className="eyebrow">A RESEARCH PROCESS YOU CAN INSPECT</div>
              <h2>
                From an open question
                <br />
                to a traceable answer.
              </h2>
              <p>
                Set an objective. Inspect the plan. Follow each source, question, and decision —
                including where evidence runs out.
              </p>
              <ol>
                <li>
                  <span>01</span>
                  <div>
                    <strong>Plan & discover</strong>
                    <p>Typed questions and explicitly scoped sources.</p>
                  </div>
                </li>
                <li>
                  <span>02</span>
                  <div>
                    <strong>Investigate & adapt</strong>
                    <p>Model-selected tools, bounded by source permissions and budgets.</p>
                  </div>
                </li>
                <li>
                  <span>03</span>
                  <div>
                    <strong>Verify & report</strong>
                    <p>Exact source quotations, conflicts, and visible unknowns.</p>
                  </div>
                </li>
              </ol>
              <div className="research-demo-note">
                <FlaskConical size={19} />
                <span>
                  The default offline demo uses synthetic fixtures. Configure a model explicitly to
                  exercise the real LLM pathway.
                </span>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
