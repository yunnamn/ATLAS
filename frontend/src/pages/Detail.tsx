import {
  ArrowLeft,
  ArrowUpRight,
  Bookmark,
  CalendarDays,
  Check,
  ChevronDown,
  Clock3,
  FileText,
  History as HistoryIcon,
  MapPin,
  PencilLine,
  ShieldCheck,
  TriangleAlert,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, deadlineDays, factValue, formatDate, labels, useResource } from '../api'
import { ErrorBox, Loading, StateBadge, SyntheticBadge, TrustNote } from '../components/ui'
import { useWorkspace } from '../components/workspace'
import type { Fact, History, Match, Opportunity } from '../types'

function ReviewForm({
  field,
  opportunity: o,
  onClose,
}: {
  field: string
  opportunity: Opportunity
  onClose: () => void
}) {
  const { refresh, notify } = useWorkspace()
  const [fact, setFact] = useState<Fact>({ ...o.facts[field] })
  const [actor, setActor] = useState('Local researcher')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api(`/opportunities/${o.id}/facts/${field}`, {
        method: 'PUT',
        body: JSON.stringify({
          fact: {
            ...fact,
            value: fact.state === 'unknown' ? null : fact.value,
            excerpt: fact.excerpt || null,
            source_id: fact.source_id || null,
          },
          actor,
          reason,
          expected_revision: o.revision,
        }),
      })
      refresh()
      notify('Evidence correction saved with revision history.')
      onClose()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="review-form" onSubmit={submit}>
      <div className="section-heading">
        <h3>Review {labels[field]}</h3>
        <button type="button" className="icon-btn" aria-label="Cancel review" onClick={onClose}>
          <X size={17} />
        </button>
      </div>
      <p className="muted">
        Review against the original source. “Reviewed” records a human assessment, not an
        independent institutional guarantee.
      </p>
      <div className="form-grid">
        <label>
          Verification state
          <select
            value={fact.state}
            onChange={(e) => setFact({ ...fact, state: e.target.value as Fact['state'] })}
          >
            <option value="unknown">Unknown</option>
            <option value="unverified">Unverified</option>
            <option value="verified">Reviewed with evidence</option>
          </select>
        </label>
        <label>
          Recorded value
          <input
            value={fact.value ?? ''}
            onChange={(e) => setFact({ ...fact, value: e.target.value })}
            disabled={fact.state === 'unknown'}
            required={fact.state !== 'unknown'}
            maxLength={2000}
          />
        </label>
        <label>
          Source
          <select
            value={fact.source_id ?? ''}
            onChange={(e) => setFact({ ...fact, source_id: e.target.value || null })}
            required={fact.state === 'verified'}
          >
            <option value="">No source selected</option>
            {o.sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
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
      </div>
      <label>
        Supporting excerpt
        <textarea
          maxLength={5000}
          value={fact.excerpt ?? ''}
          required={fact.state === 'verified'}
          onChange={(e) => setFact({ ...fact, excerpt: e.target.value })}
        />
      </label>
      <label>
        Reason for this correction
        <textarea
          minLength={5}
          maxLength={2000}
          value={reason}
          required
          onChange={(e) => setReason(e.target.value)}
          placeholder="What did you confirm or correct?"
        />
      </label>
      {field === 'funding' && (
        <small>Use: tuition_and_stipend, tuition_only, partial, or none.</small>
      )}
      {field === 'deadline' && (
        <small>Use YYYY-MM-DD. Closing time and timezone still need source review.</small>
      )}
      {error && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}
      <div className="button-row">
        <button className="btn primary" disabled={busy}>
          <Check size={15} />
          {busy ? 'Saving…' : 'Save correction'}
        </button>
        <button className="btn secondary" type="button" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  )
}
export function Detail() {
  const { id } = useParams()
  const { revision, saved, toggleSave, pending } = useWorkspace()
  const opportunity = useResource<Opportunity>(`/opportunities/${id}`, revision)
  const matching = useResource<Match>(`/opportunities/${id}/match`, revision)
  const history = useResource<History[]>(`/opportunities/${id}/history`, revision)
  const [editing, setEditing] = useState<string | null>(null)
  const [tab, setTab] = useState<'evidence' | 'history'>('evidence')
  if (opportunity.error)
    return (
      <div className="page">
        <Link className="back-link" to="/opportunities">
          <ArrowLeft size={15} />
          Back to directory
        </Link>
        <ErrorBox error={opportunity.error} />
      </div>
    )
  if (!opportunity.data) return <Loading />
  const o = opportunity.data
  const days = deadlineDays(o.facts.deadline?.value)
  const counts = { verified: 0, unverified: 0, unknown: 0 }
  Object.values(o.facts).forEach((f) => counts[f.state]++)
  return (
    <div className="page detail-page">
      <Link className="back-link" to="/opportunities">
        <ArrowLeft size={15} />
        Back to opportunities
      </Link>
      <section className="detail-header">
        <div className="detail-kicker">
          <span className="category-tag">
            {o.category === 'masters' ? 'MASTER’S OPPORTUNITY' : o.category.toUpperCase()}
          </span>
          {o.synthetic && <SyntheticBadge />}
        </div>
        <div className="detail-title-row">
          <div>
            <p className="institution-name">{o.institution}</p>
            <h1>{o.title}</h1>
            <div className="card-meta">
              <span>
                <MapPin size={14} />
                {o.country}
              </span>
              <span>Revision {o.revision}</span>
              <span>Updated {formatDate(o.updated_at)}</span>
            </div>
          </div>
          <button
            className={`btn ${saved.has(o.id) ? 'secondary' : 'primary'}`}
            disabled={pending === o.id}
            onClick={() => toggleSave(o.id)}
          >
            <Bookmark size={16} fill={saved.has(o.id) ? 'currentColor' : 'none'} />
            {saved.has(o.id) ? 'Saved to shortlist' : 'Save opportunity'}
          </button>
        </div>
        {o.synthetic && (
          <div className="synthetic-notice">
            <TriangleAlert size={17} />
            <span>
              <strong>This is a synthetic demonstration.</strong> The institution, award,
              requirements, and excerpts are invented examples. Do not apply or rely on them as real
              research.
            </span>
          </div>
        )}
      </section>
      <div className="detail-grid">
        <div className="detail-main">
          <section className="panel">
            <div className="eyebrow">THE OPPORTUNITY</div>
            <h2>A closer look</h2>
            <p className="detail-summary">{o.summary}</p>
            <div className="tags">
              {o.subjects.map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
            <div className="funding-overview">
              <div>
                <small>RECORDED FUNDING</small>
                <strong>{factValue(o.facts.funding?.value)}</strong>
                <StateBadge state={o.facts.funding?.state ?? 'unknown'} />
              </div>
              <div>
                <small>APPLICATION FEE</small>
                <strong>{factValue(o.facts.application_fee?.value)}</strong>
                <StateBadge state={o.facts.application_fee?.state ?? 'unknown'} />
              </div>
            </div>
          </section>
          <section className="panel evidence-panel" id="evidence">
            <div className="section-heading">
              <div>
                <div className="eyebrow">TRANSPARENT BY DESIGN</div>
                <h2>The evidence behind the details</h2>
              </div>
              <ShieldCheck size={22} />
            </div>
            <p className="muted">
              Values, source excerpts, and gaps. Open a field to inspect its provenance or make a
              correction.
            </p>
            <div className="evidence-summary">
              <span>
                <b>{counts.verified}</b> reviewed
              </span>
              <span>
                <b>{counts.unverified}</b> unverified
              </span>
              <span>
                <b>{counts.unknown}</b> unknown
              </span>
            </div>
            <div className="tabs" role="tablist" aria-label="Record information">
              <button
                role="tab"
                aria-selected={tab === 'evidence'}
                aria-controls="evidence-tab"
                onClick={() => setTab('evidence')}
              >
                <FileText size={15} />
                Fields & sources
              </button>
              <button
                role="tab"
                aria-selected={tab === 'history'}
                aria-controls="history-tab"
                onClick={() => setTab('history')}
              >
                <HistoryIcon size={15} />
                Revision history
              </button>
            </div>
            {tab === 'evidence' ? (
              <div role="tabpanel" id="evidence-tab">
                {Object.entries(o.facts).map(([key, fact]) => (
                  <details className="fact-row" key={`${o.revision}-${key}`}>
                    <summary>
                      <div>
                        <strong>{labels[key] ?? key}</strong>
                        <span>
                          {key === 'deadline' && fact.value
                            ? formatDate(fact.value)
                            : factValue(fact.value)}
                        </span>
                      </div>
                      <StateBadge state={fact.state} />
                      <ChevronDown size={15} />
                    </summary>
                    <div className="fact-evidence">
                      {fact.excerpt ? (
                        <blockquote>{fact.excerpt}</blockquote>
                      ) : (
                        <p className="muted">
                          No supporting excerpt recorded. This field needs further research.
                        </p>
                      )}
                      {fact.source_id &&
                        (() => {
                          const source = o.sources.find((s) => s.id === fact.source_id)
                          return (
                            source && (
                              <div className="source-reference">
                                <FileText size={15} />
                                <span>
                                  {source.label}
                                  <small>
                                    {source.kind === 'demo'
                                      ? 'Synthetic example · not an official citation'
                                      : `Imported ${source.kind.replace('_', ' ')} · official status ${source.official_asserted ? 'asserted by importer' : 'not established'}`}
                                  </small>
                                </span>
                                {source.url && (
                                  <a href={source.url} target="_blank" rel="noreferrer">
                                    Open source <ArrowUpRight size={13} />
                                  </a>
                                )}
                              </div>
                            )
                          )
                        })()}
                      <button className="btn secondary btn-small" onClick={() => setEditing(key)}>
                        <PencilLine size={13} />
                        Review / correct
                      </button>
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <div role="tabpanel" id="history-tab">
                {history.error ? (
                  <ErrorBox error={history.error} />
                ) : history.loading ? (
                  <Loading />
                ) : (
                  history.data?.map((h) => (
                    <div className="history-item" key={h.id}>
                      <span className="activity-icon">
                        <Clock3 size={15} />
                      </span>
                      <div>
                        <strong>
                          Revision {h.revision} · {h.actor}
                        </strong>
                        <p>{h.reason}</p>
                        {h.before && (
                          <small>
                            Changed:{' '}
                            {Object.keys(h.after.facts)
                              .filter(
                                (k) =>
                                  JSON.stringify(h.before?.facts[k]) !==
                                  JSON.stringify(h.after.facts[k]),
                              )
                              .map((k) => labels[k] ?? k)
                              .join(', ')}
                          </small>
                        )}
                        <time>
                          {formatDate(h.created_at)} ·{' '}
                          {new Date(
                            h.created_at.endsWith('Z') || /[+-]\d\d:\d\d$/.test(h.created_at)
                              ? h.created_at
                              : `${h.created_at}Z`,
                          ).toLocaleTimeString()}
                        </time>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
            {editing && (
              <ReviewForm
                key={`${editing}-${o.revision}`}
                field={editing}
                opportunity={o}
                onClose={() => setEditing(null)}
              />
            )}
          </section>
          <section className="panel">
            <h2>Source registry</h2>
            <p className="muted">
              Source timestamps reflect the supplied retrieval date, not the import time. Official
              status is an importer assertion.
            </p>
            {o.sources.length ? (
              o.sources.map((s) => (
                <div className="registry-row" key={s.id}>
                  <FileText size={19} />
                  <div>
                    <strong>{s.label}</strong>
                    <p>
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.url} <ArrowUpRight size={12} />
                        </a>
                      ) : (
                        'No website URL supplied'
                      )}
                    </p>
                    <small>
                      Retrieved: {formatDate(s.retrieved_at)} · Type: {s.kind}
                    </small>
                    {s.content_sha256 && (
                      <code className="source-hash">SHA-256: {s.content_sha256}</code>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <p>No sources attached. Add an evidence-linked record through import.</p>
            )}
          </section>
        </div>
        <aside className="detail-side">
          <section className="panel deadline-panel">
            <div className="section-heading">
              <span className="eyebrow">APPLICATION TIMELINE</span>
              <CalendarDays size={19} />
            </div>
            <h2>{formatDate(o.facts.deadline?.value)}</h2>
            <StateBadge state={o.facts.deadline?.state ?? 'unknown'} />
            {days !== null && (
              <p className={days < 0 ? 'deadline-expired' : ''}>
                {days < 0
                  ? 'Recorded deadline has passed'
                  : `${days} calendar days to recorded deadline`}
              </p>
            )}
            <small>Closing time and timezone are not recorded. Confirm both with the source.</small>
          </section>
          <section className="panel match-panel">
            <div className="section-heading">
              <h2>How does it fit?</h2>
              <ShieldCheck size={19} />
            </div>
            {matching.error ? (
              <ErrorBox error={matching.error} />
            ) : matching.data ? (
              <>
                <div className="fit-score">
                  <strong>
                    {matching.data.score ?? '—'}
                    <small>{matching.data.score !== null && '/100'}</small>
                  </strong>
                  <div>
                    Preference fit<span>Recorded rules only</span>
                  </div>
                </div>
                <div className="fit-track">
                  <span style={{ width: `${matching.data.score ?? 0}%` }} />
                </div>
                <p className="fit-disclaimer">{matching.data.disclaimer}</p>
                <div className="eligibility-label">
                  {matching.data.eligibility === 'rules_met'
                    ? 'Recorded requirements met'
                    : matching.data.eligibility === 'requirement_gap'
                      ? 'A reviewed requirement has a gap'
                      : 'Eligibility needs review'}
                </div>
                <div className="match-checks">
                  {matching.data.checks.map((check, i) => (
                    <details key={i}>
                      <summary>
                        <span className={`check-symbol outcome-${check.outcome}`}>
                          {check.outcome === 'match'
                            ? '✓'
                            : check.outcome.includes('gap')
                              ? '!'
                              : '?'}
                        </span>
                        <span>
                          {labels[check.label] ?? check.label}
                          <small>
                            {check.kind} · {check.outcome.replaceAll('_', ' ')}
                          </small>
                        </span>
                        <ChevronDown size={12} />
                      </summary>
                      <p>{check.detail}</p>
                    </details>
                  ))}
                </div>
                {matching.data.warnings.length > 0 && (
                  <div className="risk-list">
                    <h3>
                      <TriangleAlert size={14} />
                      Conditions to investigate
                    </h3>
                    {matching.data.warnings.map((w) => (
                      <p key={w}>• {w}</p>
                    ))}
                  </div>
                )}
                <Link className="text-link" to="/profile">
                  Edit your profile <ArrowUpRight size={14} />
                </Link>
              </>
            ) : (
              <Loading />
            )}
          </section>
          <TrustNote />
        </aside>
      </div>
    </div>
  )
}
