import {
  AlertCircle,
  ArrowUpRight,
  Bookmark,
  CalendarDays,
  MapPin,
  Plus,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { factValue, formatDate } from '../api'
import type { Opportunity } from '../types'
import { useWorkspace } from './workspace'

export function StateBadge({ state }: { state: string }) {
  return (
    <span className={`badge state-${state}`}>
      <span className="status-dot" />
      {state === 'verified'
        ? 'Reviewed · evidence linked'
        : state === 'unknown'
          ? 'Unknown'
          : 'Unverified'}
    </span>
  )
}
export function SyntheticBadge() {
  return (
    <span className="demo-tag">
      <Sparkles size={11} /> Synthetic demo
    </span>
  )
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" /> Loading your workspace…
    </div>
  )
}
export function ErrorBox({ error }: { error: string }) {
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={20} />
      <div>
        <strong>We couldn’t complete that request.</strong>
        <p>{error}</p>
        <small>Check that the API is running, then try again.</small>
      </div>
    </div>
  )
}
export function Empty({
  title = 'A world of possibilities starts here.',
  text = 'Import the synthetic collection to explore the workspace, or add your own research.',
  action = true,
}: {
  title?: string
  text?: string
  action?: boolean
}) {
  const { openImport, seed, busy } = useWorkspace()
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Sparkles size={27} />
      </div>
      <h2>{title}</h2>
      <p>{text}</p>
      {action && (
        <div className="button-row">
          <button className="btn primary" onClick={seed} disabled={busy}>
            Load synthetic demo
          </button>
          <button className="btn secondary" onClick={openImport}>
            <Plus size={16} /> Import research
          </button>
        </div>
      )}
    </div>
  )
}
export function OpportunityCard({
  opportunity: o,
  selected,
  onCompare,
}: {
  opportunity: Opportunity
  selected?: boolean
  onCompare?: () => void
}) {
  const { saved, toggleSave, pending } = useWorkspace()
  const full = o.facts.funding?.value === 'tuition_and_stipend'
  return (
    <article className="opportunity-card">
      <div className="card-top">
        <span className={`institution-monogram country-${o.country.replaceAll(' ', '-')}`}>
          {o.institution
            .split(' ')
            .slice(0, 2)
            .map((w) => w[0])
            .join('')}
        </span>
        <div className="card-labels">
          <span className={`funding-tag ${full ? 'full' : ''}`}>
            {factValue(o.facts.funding?.value)}
          </span>
          {o.synthetic && <SyntheticBadge />}
        </div>
        <button
          className={`icon-btn bookmark ${saved.has(o.id) ? 'is-saved' : ''}`}
          aria-label={`${saved.has(o.id) ? 'Unsave' : 'Save'} ${o.title}`}
          aria-pressed={saved.has(o.id)}
          onClick={() => toggleSave(o.id)}
          disabled={pending === o.id}
        >
          <Bookmark size={19} fill={saved.has(o.id) ? 'currentColor' : 'none'} />
        </button>
      </div>
      <p className="institution-name">{o.institution}</p>
      <Link className="card-title" to={`/opportunities/${o.id}`}>
        {o.title}
      </Link>
      <div className="card-meta">
        <span>
          <MapPin size={13} />
          {o.country}
        </span>
        <span>
          {{
            masters: 'Master’s degree',
            fellowship: 'Fellowship',
            hackathon: 'Hackathon',
            job: 'Job',
          }[o.category] ?? o.category}
        </span>
      </div>
      <p className="card-summary">{o.summary}</p>
      <div className="tags">
        {o.subjects.slice(0, 2).map((s) => (
          <span key={s}>{s}</span>
        ))}
      </div>
      <div className="card-bottom">
        <span>
          <CalendarDays size={14} />
          {formatDate(o.facts.deadline?.value)}
        </span>
        <Link to={`/opportunities/${o.id}`} aria-label={`View ${o.title}`}>
          <ArrowUpRight size={19} />
        </Link>
      </div>
      {onCompare && (
        <label className="compare-checkbox">
          <input type="checkbox" checked={selected} onChange={onCompare} /> Compare opportunity
        </label>
      )}
    </article>
  )
}
export function TrustNote() {
  return (
    <div className="trust-note">
      <ShieldCheck size={20} />
      <div>
        <strong>Evidence before assumptions.</strong>
        <p>
          A listed benefit is a claim to check. Review its original source, funding exclusions, and
          eligibility before applying.
        </p>
      </div>
    </div>
  )
}
