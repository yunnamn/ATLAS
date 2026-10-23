import { ArrowUpRight, FileSearch, Plus, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDate, useResource } from '../api'
import { Empty, ErrorBox, Loading, SyntheticBadge, TrustNote } from '../components/ui'
import { useWorkspace } from '../components/workspace'
import type { Directory } from '../types'

export function Sources() {
  const { revision, openImport } = useWorkspace()
  const { data, error, loading } = useResource<Directory>('/opportunities?limit=100', revision)
  const totals = data?.items.reduce(
    (result, o) => {
      Object.values(o.facts).forEach((f) => result[f.state]++)
      return result
    },
    { verified: 0, unverified: 0, unknown: 0 },
  )
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">TRUST IS IN THE DETAILS</div>
          <h1>Know what you know.</h1>
          <p>Trace every claim. Close the gaps. Keep your research accountable.</p>
        </div>
        <button className="btn primary" onClick={openImport}>
          <Plus size={16} />
          Import source
        </button>
      </div>
      <div className="verification-banner">
        <span className="verification-icon">
          <ShieldCheck size={32} strokeWidth={1.4} />
        </span>
        <div>
          <h2>A citation is the start, not the finish.</h2>
          <p>
            Imports enter as unverified. Human review links a field to supporting evidence.
            <br />
            Unknown values remain visible until the source can establish them.
          </p>
        </div>
      </div>
      <div className="verification-stats">
        {[
          ['verified', 'Reviewed with evidence'],
          ['unverified', 'Unverified claims'],
          ['unknown', 'Unknown fields'],
        ].map(([key, label]) => (
          <div key={key}>
            <span className={`status-dot dot-${key}`} />
            <strong>{totals?.[key as keyof typeof totals] ?? '—'}</strong>
            <span>{label}</span>
          </div>
        ))}
      </div>
      <div className="section-heading">
        <h2>Evidence review queue</h2>
        <span className="muted">{data?.items.length ?? 0} records</span>
      </div>
      {error ? (
        <ErrorBox error={error} />
      ) : loading ? (
        <Loading />
      ) : data?.items.length ? (
        <section className="panel source-queue">
          {data.items.map((o) => {
            const facts = Object.values(o.facts)
            const reviewed = facts.filter((f) => f.state === 'verified').length
            return (
              <article key={o.id} className="source-queue-row">
                <span className="activity-icon">
                  <FileSearch size={20} />
                </span>
                <div className="source-queue-title">
                  <Link to={`/opportunities/${o.id}#evidence`}>{o.title}</Link>
                  <p>
                    {o.sources.length} source{o.sources.length !== 1 ? 's' : ''} · Imported{' '}
                    {formatDate(o.created_at)}
                  </p>
                  {o.synthetic && <SyntheticBadge />}
                </div>
                <div className="review-progress">
                  <span>
                    {reviewed} of {facts.length} fields reviewed
                  </span>
                  <div>
                    <i style={{ width: `${(reviewed / facts.length) * 100}%` }} />
                  </div>
                  <small>
                    {facts.filter((f) => f.state === 'unknown').length} unknown ·{' '}
                    {facts.filter((f) => f.state === 'unverified').length} unverified
                  </small>
                </div>
                <Link className="btn secondary btn-small" to={`/opportunities/${o.id}#evidence`}>
                  Review evidence <ArrowUpRight size={14} />
                </Link>
              </article>
            )
          })}
        </section>
      ) : (
        <Empty />
      )}
      <div className="source-notes">
        <TrustNote />
        <div className="trust-note">
          <FileSearch size={20} />
          <div>
            <strong>Research at your pace.</strong>
            <p>
              Only explicit imports are processed. Automatic URL retrieval and scheduled
              source-change detection are future milestones; no background crawling runs.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
