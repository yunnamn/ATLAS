import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, factValue, labels, useResource } from '../api'
import type {
  ResearchClaim,
  ResearchEvidence,
  ResearchReport,
  SupportAssessment,
} from '../research'
import type { Directory, Fact } from '../types'
import { SavedSource } from './ResearchSource'
import { ErrorBox, Loading } from './ui'
import { useWorkspace } from './workspace'

interface Proposal {
  id: string
  status: string
  revision: number
  target_opportunity_id: number | null
  expected_opportunity_revision: number | null
  content: {
    synthetic: boolean
    identity: { title: string; institution: string; country: string } | null
    scope: ResearchClaim['scope']
    changes: {
      field: string
      before: Fact | null
      after: Fact
      evidence: {
        document_id: string
        quote: string
        scope_quote: string
        source_hash: string
        url: string
        semantic_assessment: SupportAssessment
      }[]
    }[]
    blocked: { field: string; reason: string }[]
  }
  approval: { actor: string; opportunity_id: number; selected_fields: string[] } | null
}

function ProposalCard({
  proposal: p,
  runId,
  evidence,
  changed,
}: {
  proposal: Proposal
  runId: string
  evidence: ResearchEvidence
  changed: () => void
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [actor, setActor] = useState('')
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [documentId, setDocumentId] = useState<string | null>(null)
  const { notify } = useWorkspace()
  const document = evidence.documents.find((d) => d.id === documentId)
  async function approve(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api(`/research/runs/${runId}/proposals/${p.id}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: p.revision,
          selected_fields: [...selected],
          actor,
          reason,
          confirm_source_review: confirmed,
        }),
      })
      notify('Selected changes approved and saved with evidence and revision history.')
      changed()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <article className="research-proposal">
      <h3>{p.content.identity?.title ?? `Update opportunity #${p.target_opportunity_id}`}</h3>
      <p>
        {p.content.scope.program} · {p.content.scope.intake_year ?? 'Intake unknown'} · {p.status}
      </p>
      {p.content.synthetic && (
        <p className="research-demo-note">
          Synthetic demonstration. This label is preserved in the directory.
        </p>
      )}
      {p.content.identity ? (
        <p className="muted">
          Reviewer-supplied identity: {p.content.identity.institution} ·{' '}
          {p.content.identity.country}
        </p>
      ) : (
        <p className="muted">
          Based on opportunity revision {p.expected_opportunity_revision}. Approval fails if it has
          changed.
        </p>
      )}
      <form onSubmit={approve}>
        <div className="research-proposal-changes">
          {p.content.changes.map((change) => (
            <section key={change.field}>
              <label className="checkbox-panel">
                {p.status === 'pending' && (
                  <input
                    type="checkbox"
                    checked={selected.has(change.field)}
                    onChange={(e) => {
                      setSelected((previous) => {
                        const next = new Set(previous)
                        if (e.target.checked) next.add(change.field)
                        else next.delete(change.field)
                        return next
                      })
                    }}
                  />
                )}
                <span>
                  <strong>{labels[change.field] ?? change.field}</strong>
                  <br />
                  Before: {factValue(change.before?.value)}{' '}
                  {change.before && `(${change.before.state})`}
                  <br />
                  Proposed: {factValue(change.after.value)}
                </span>
              </label>
              <details>
                <summary>Inspect evidence for {labels[change.field] ?? change.field}</summary>
                {change.evidence.map((source, index) => (
                  <div key={index} className="research-proposal-source">
                    <p className="research-url">{source.url}</p>
                    <blockquote>{source.quote}</blockquote>
                    <p>Scope: {source.scope_quote}</p>
                    <p className="muted">
                      Support screen: {source.semantic_assessment.label?.replaceAll('_', ' ')}.
                      Human review is required.
                    </p>
                    <code className="source-hash">SHA-256 {source.source_hash}</code>
                    <button
                      type="button"
                      className="text-link"
                      onClick={() => setDocumentId(source.document_id)}
                    >
                      Inspect full saved source
                    </button>
                  </div>
                ))}
              </details>
            </section>
          ))}
        </div>
        {p.content.blocked.length > 0 && (
          <details>
            <summary>Fields excluded from approval</summary>
            {p.content.blocked.map((item, i) => (
              <p key={i}>
                {labels[item.field] ?? item.field}: {item.reason}
              </p>
            ))}
          </details>
        )}
        {p.status === 'pending' ? (
          <>
            <div className="form-grid">
              <label>
                Reviewer name
                <input
                  required
                  minLength={2}
                  maxLength={100}
                  value={actor}
                  onChange={(e) => setActor(e.target.value)}
                />
              </label>
              <label>
                Review reason
                <input
                  required
                  minLength={5}
                  maxLength={1500}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
            </div>
            <label className="checkbox-panel">
              <input
                type="checkbox"
                required
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>
                I inspected the selected citations, scope, conditions, and proposed changes. I
                approve saving them as human-reviewed facts.
              </span>
            </label>
            <p className="muted">
              Only checked fields will be saved. “Verified” records this local human review;
              reviewer identity and source truth are not authenticated.
            </p>
            <button className="btn primary" disabled={busy || !confirmed || selected.size === 0}>
              {busy ? 'Saving…' : 'Approve selected changes'}
            </button>
          </>
        ) : (
          p.approval && (
            <p>
              Approved by {p.approval.actor}.{' '}
              <Link className="text-link" to={`/opportunities/${p.approval.opportunity_id}`}>
                Open saved opportunity
              </Link>
            </p>
          )
        )}
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
      </form>
      {document && (
        <SavedSource runId={runId} document={document} close={() => setDocumentId(null)} />
      )}
    </article>
  )
}

export function ResearchReview({
  runId,
  evidence,
  report,
}: {
  runId: string
  evidence: ResearchEvidence
  report: ResearchReport
}) {
  const { refresh, revision: workspaceRevision } = useWorkspace()
  const [revision, setRevision] = useState(0)
  const proposals = useResource<Proposal[]>(`/research/runs/${runId}/proposals`, revision)
  const directory = useResource<Directory>('/opportunities?limit=100', workspaceRevision)
  const [scopeIndex, setScopeIndex] = useState('0')
  const [target, setTarget] = useState('new')
  const scope = report.investigated_opportunities[Number(scopeIndex)]
  const initialInstitution =
    evidence.claims.find((c) => c.field === 'institution' && c.state !== 'unverified')?.value ?? ''
  const [identity, setIdentity] = useState({
    external_id: '',
    title: scope?.program ?? '',
    institution: initialInstitution,
    country: '',
    summary: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  function changed() {
    setRevision((r) => r + 1)
    refresh()
  }
  async function propose(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const row = directory.data?.items.find((o) => String(o.id) === target)
    try {
      await api(`/research/runs/${runId}/proposals`, {
        method: 'POST',
        body: JSON.stringify({
          scope,
          ...(target === 'new'
            ? { identity }
            : {
                target_opportunity_id: Number(target),
                expected_opportunity_revision: row?.revision,
              }),
        }),
      })
      setRevision((r) => r + 1)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="research-review">
      <h2>Review proposed changes</h2>
      <p>
        Prepare a proposal, inspect each source, then select fields to approve. Preparing a proposal
        does not change the directory.
      </p>
      {report.investigated_opportunities.length > 0 ? (
        <form className="research-proposal-form" onSubmit={propose}>
          <div className="form-grid">
            <label>
              Research scope
              <select value={scopeIndex} onChange={(e) => setScopeIndex(e.target.value)}>
                {report.investigated_opportunities.map((s, i) => (
                  <option key={i} value={i}>
                    {s.program} · {s.intake_year ?? 'unknown'}
                    {s.award_track ? ` · ${s.award_track}` : ''}
                    {s.applicant_group ? ` · ${s.applicant_group}` : ''}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Save destination
              <select value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="new">Create a new opportunity</option>
                {directory.data?.items.map((o) => (
                  <option value={o.id} key={o.id}>
                    Update #{o.id}: {o.title} · revision {o.revision}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {target === 'new' && (
            <>
              <p className="muted">
                Confirm record identity and destination yourself; these fields are not inferred from
                funding claims.
              </p>
              <div className="form-grid">
                {(
                  [
                    ['external_id', 'Unique record identifier', 1, 120],
                    ['title', 'Opportunity title', 3, 200],
                    ['institution', 'Institution', 2, 200],
                    ['country', 'Destination country', 2, 80],
                  ] as const
                ).map(([key, label, min, max]) => (
                  <label key={key}>
                    {label}
                    <input
                      required
                      minLength={min}
                      maxLength={max}
                      value={identity[key]}
                      onChange={(e) => setIdentity((p) => ({ ...p, [key]: e.target.value }))}
                    />
                  </label>
                ))}
              </div>
              <label>
                Record summary
                <textarea
                  required
                  minLength={10}
                  maxLength={5000}
                  value={identity.summary}
                  onChange={(e) => setIdentity((p) => ({ ...p, summary: e.target.value }))}
                />
              </label>
            </>
          )}
          <button className="btn secondary" disabled={busy}>
            {busy ? 'Preparing…' : 'Prepare review proposal'}
          </button>
          {error && (
            <div className="inline-error" role="alert">
              {error}
            </div>
          )}
        </form>
      ) : (
        <p className="muted">No supported program scope is available to propose.</p>
      )}
      {directory.error && <ErrorBox error={directory.error} />}
      {proposals.error ? (
        <ErrorBox error={proposals.error} />
      ) : proposals.loading ? (
        <Loading />
      ) : (
        proposals.data?.map((p) => (
          <ProposalCard
            key={`${p.id}:${p.revision}`}
            proposal={p}
            runId={runId}
            evidence={evidence}
            changed={changed}
          />
        ))
      )}
    </section>
  )
}
