import { ArrowUpRight, Bookmark, Save, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { api, formatDate } from '../api'
import { Empty, ErrorBox, Loading, SyntheticBadge } from '../components/ui'
import { useWorkspace } from '../components/workspace'
import type { Application } from '../types'

const statuses = ['saved', 'preparing', 'submitted', 'accepted', 'closed']
function ApplicationRow({ application: a }: { application: Application }) {
  const { refresh, toggleSave, notify, pending } = useWorkspace()
  const [editing, setEditing] = useState(false)
  const [status, setStatus] = useState(a.status)
  const [notes, setNotes] = useState(a.notes)
  const [missing, setMissing] = useState(a.missing_requirements.join('\n'))
  const [busy, setBusy] = useState(false)
  async function save(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await api(`/applications/${a.opportunity_id}`, {
        method: 'PUT',
        body: JSON.stringify({
          status,
          notes,
          missing_requirements: missing
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      })
      refresh()
      setEditing(false)
      notify('Application updated.')
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <article className="panel application-row">
      <div className="application-summary">
        <span className="institution-monogram">
          {a.opportunity.institution.slice(0, 2).toUpperCase()}
        </span>
        <div className="application-title">
          <Link to={`/opportunities/${a.opportunity_id}`}>
            {a.opportunity.title}
            <ArrowUpRight size={15} />
          </Link>
          <p>
            {a.opportunity.institution} · {a.opportunity.country}
          </p>
          {a.opportunity.synthetic && <SyntheticBadge />}
        </div>
        <div className="application-deadline">
          <small>RECORDED DEADLINE</small>
          <strong>{formatDate(a.opportunity.facts.deadline?.value)}</strong>
          <small>{a.opportunity.facts.deadline?.state ?? 'unknown'} · confirm timezone</small>
        </div>
        <span className={`application-status status-${a.status}`}>{a.status}</span>
        <button className="btn secondary btn-small" onClick={() => setEditing(!editing)}>
          {editing ? 'Close editor' : 'Manage'}
        </button>
        <button
          className="icon-btn"
          aria-label={`Remove ${a.opportunity.title} from shortlist`}
          disabled={pending === a.opportunity_id}
          onClick={() => toggleSave(a.opportunity_id)}
        >
          <Trash2 size={16} />
        </button>
      </div>
      {a.missing_requirements.length > 0 && (
        <div className="missing-list">
          <small>TO PREPARE</small>
          {a.missing_requirements.map((m, i) => (
            <span key={i}>{m}</span>
          ))}
        </div>
      )}
      {a.notes && !editing && <p className="application-notes">{a.notes}</p>}
      {editing && (
        <form className="application-editor" onSubmit={save}>
          <div className="form-grid">
            <label>
              Application status
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                {statuses.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Missing requirements (one per line)
              <textarea
                value={missing}
                onChange={(e) => setMissing(e.target.value)}
                placeholder="Language certificate&#10;Statement of purpose"
              />
            </label>
          </div>
          <label>
            Private research notes
            <textarea maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <button className="btn primary btn-small" disabled={busy}>
            <Save size={14} />
            {busy ? 'Saving…' : 'Update application'}
          </button>
        </form>
      )}
    </article>
  )
}
export function Saved() {
  const { applications, applicationsLoading, applicationsError } = useWorkspace()
  const [filter, setFilter] = useState('all')
  const shown = applications.filter((a) => filter === 'all' || a.status === filter)
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">TURN RESEARCH INTO MOMENTUM</div>
          <h1>Your next moves.</h1>
          <p>A considered shortlist. A clear application pipeline. One step closer.</p>
        </div>
        <Link to="/opportunities" className="btn primary">
          <Bookmark size={15} />
          Explore opportunities
        </Link>
      </div>
      <div className="pipeline-stats">
        {['saved', 'preparing', 'submitted', 'accepted'].map((s) => (
          <button
            key={s}
            className={filter === s ? 'selected' : ''}
            onClick={() => setFilter(filter === s ? 'all' : s)}
          >
            <strong>
              {applications
                .filter((a) => a.status === s)
                .length.toString()
                .padStart(2, '0')}
            </strong>
            <span>{s}</span>
          </button>
        ))}
      </div>
      <div className="section-heading">
        <h2>
          {filter === 'all'
            ? 'Your application pipeline'
            : `${filter.charAt(0).toUpperCase() + filter.slice(1)} applications`}
        </h2>
        {filter !== 'all' && (
          <button className="text-link" onClick={() => setFilter('all')}>
            Show all
          </button>
        )}
      </div>
      {applicationsError ? (
        <ErrorBox error={applicationsError} />
      ) : applicationsLoading ? (
        <Loading />
      ) : shown.length ? (
        <div className="applications-list">
          {shown.map((a) => (
            <ApplicationRow key={`${a.id}-${a.updated_at}`} application={a} />
          ))}
        </div>
      ) : (
        <Empty
          title="Make room for your next chapter."
          text={
            filter === 'all'
              ? 'Save an opportunity from the directory to start tracking your application and missing requirements.'
              : 'There are no applications at this stage yet.'
          }
          action={false}
        />
      )}
    </div>
  )
}
