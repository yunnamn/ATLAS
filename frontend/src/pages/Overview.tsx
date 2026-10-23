import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  Check,
  Compass,
  Files,
  Globe2,
  Plus,
  ShieldCheck,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useResource, formatDate } from '../api'
import { Empty, ErrorBox, Loading, OpportunityCard } from '../components/ui'
import { useWorkspace } from '../components/workspace'
import type { Directory } from '../types'

function OrbitalGlobe() {
  return (
    <div className="globe-art" aria-hidden="true">
      <div className="orbit-label label-a">
        <span /> A WORLD OF POSSIBILITY
      </div>
      <svg viewBox="0 0 360 270" fill="none">
        <g transform="translate(180 137) rotate(-18)">
          <circle r="101" stroke="currentColor" />
          <ellipse rx="48" ry="101" stroke="currentColor" />
          <ellipse rx="82" ry="101" stroke="currentColor" />
          <ellipse rx="101" ry="38" stroke="currentColor" />
          <ellipse rx="101" ry="73" stroke="currentColor" />
          <path d="M-101 0h202M0-101v202" stroke="currentColor" />
          <ellipse
            rx="157"
            ry="44"
            transform="rotate(-25)"
            stroke="currentColor"
            strokeDasharray="3 5"
          />
          <circle cx="-98" cy="-8" r="5" fill="#bdcf9a" stroke="#244b42" strokeWidth="5" />
          <circle cx="77" cy="-64" r="5" fill="#bdcf9a" stroke="#244b42" strokeWidth="5" />
        </g>
        <path d="m268 65 43-18h25M82 154l-28 34H20" stroke="currentColor" />
        <circle cx="268" cy="65" r="3" fill="#dbe8bd" />
      </svg>
      <div className="orbit-label label-b">
        RESEARCH WITHOUT BORDERS <ArrowUpRight size={12} />
      </div>
    </div>
  )
}
export function Overview() {
  const { revision, saved, applications, openImport } = useWorkspace()
  const { data, error, loading } = useResource<Directory>('/opportunities?limit=100', revision)
  const funded =
    data?.items.filter((o) => o.facts.funding?.value === 'tuition_and_stipend').length ?? 0
  const pending =
    data?.items.reduce(
      (sum, o) => sum + Object.values(o.facts).filter((f) => f.state === 'unverified').length,
      0,
    ) ?? 0
  return (
    <div className="page overview-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="tiny-line" />
            YOUR NEXT CHAPTER
          </div>
          <h1>A little direction. A world of possibility.</h1>
          <p>Your research, opportunities, and next steps — all in one thoughtful space.</p>
        </div>
        <span className="workspace-status">
          <span className="online-dot" /> Local research workspace
        </span>
      </div>
      <section className="hero">
        <div className="hero-content">
          <span className="hero-kicker">
            <Globe2 size={14} /> GO BEYOND THE SEARCH
          </span>
          <h2>
            Big ambitions.
            <br />
            <em>Grounded in evidence.</em>
          </h2>
          <p>
            Discover funded master’s opportunities.
            <br />
            Understand the details. Make your next move with clarity.
          </p>
          <Link className="btn hero-button" to="/opportunities">
            Explore opportunities <ArrowUpRight size={17} />
          </Link>
          <div className="hero-caption">
            <ShieldCheck size={13} /> Transparent sources. No admissions predictions.
          </div>
        </div>
        <OrbitalGlobe />
      </section>
      {error && <ErrorBox error={error} />}
      <section className="stats-grid" aria-label="Workspace statistics">
        <div className="stat-card">
          <span className="stat-icon">
            <Compass size={20} />
          </span>
          <div>
            <p>Opportunities in your library</p>
            <strong>{data?.total_all ?? '—'}</strong>
            <small>Across {data?.countries.length ?? 0} destinations</small>
          </div>
          <ArrowUpRight className="stat-arrow" size={17} />
        </div>
        <div className="stat-card">
          <span className="stat-icon warm">
            <Globe2 size={20} />
          </span>
          <div>
            <p>Tuition + living support</p>
            <strong>{funded.toString().padStart(2, '0')}</strong>
            <small>Recorded claims · verification required</small>
          </div>
          <ShieldCheck className="stat-arrow" size={17} />
        </div>
        <div className="stat-card">
          <span className="stat-icon purple">
            <Bookmark size={20} />
          </span>
          <div>
            <p>In your application pipeline</p>
            <strong>{saved.size.toString().padStart(2, '0')}</strong>
            <small>
              {applications.filter((a) => a.status === 'preparing').length} currently in preparation
            </small>
          </div>
          <ArrowDownRight className="stat-arrow" size={17} />
        </div>
      </section>
      <section>
        <div className="section-heading">
          <div>
            <div className="eyebrow">THE EXPLORATION STARTS HERE</div>
            <h2>
              Opportunities to look closer at<span className="subtle-dot">.</span>
            </h2>
          </div>
          <Link className="text-link" to="/opportunities">
            View directory <ArrowRight size={16} />
          </Link>
        </div>
        <p className="section-description">
          {data?.items.every((o) => o.synthetic) && data.items.length > 0
            ? 'A synthetic collection for exploring ATLAS. These are not real programs or awards.'
            : 'Your research library, with evidence and uncertainty kept in view.'}
        </p>
        {loading ? (
          <Loading />
        ) : data && data.items.length ? (
          <div className="cards-grid overview-cards">
            {data.items.slice(0, 3).map((o) => (
              <OpportunityCard key={o.id} opportunity={o} />
            ))}
          </div>
        ) : (
          !error && <Empty />
        )}
      </section>
      <div className="overview-bottom">
        <section className="panel research-panel">
          <div className="section-heading">
            <h2>Your research, with context</h2>
            <Files size={20} />
          </div>
          <div className="activity-row">
            <span className="activity-icon">
              <Files size={17} />
            </span>
            <div>
              <strong>{pending} recorded claims need review</strong>
              <p>Read the excerpts and confirm against the original source.</p>
            </div>
            <Link to="/sources" className="icon-btn" aria-label="Review sources">
              <ArrowUpRight size={18} />
            </Link>
          </div>
          <div className="activity-row">
            <span className="activity-icon warm">
              <Compass size={17} />
            </span>
            <div>
              <strong>{data?.countries.length ?? 0} destinations in your library</strong>
              <p>Compare funding, conditions, and what’s still unknown.</p>
            </div>
            <Link to="/opportunities" className="icon-btn" aria-label="Explore directory">
              <ArrowUpRight size={18} />
            </Link>
          </div>
          <div className="activity-row">
            <span className="activity-icon">
              <Plus size={17} />
            </span>
            <div>
              <strong>Bring your own research</strong>
              <p>Add a structured record, a local PDF, or source text.</p>
            </div>
            <button onClick={openImport} className="icon-btn" aria-label="Import research">
              <Plus size={18} />
            </button>
          </div>
        </section>
        <section className="panel next-panel">
          <div className="eyebrow">MAKE IT YOURS</div>
          <h2>
            A clearer path starts
            <br />
            with your profile.
          </h2>
          <p>
            Add your background and priorities for transparent, rule-based compatibility checks.
          </p>
          <ul>
            <li>
              <Check size={14} /> Separate requirements from preferences
            </li>
            <li>
              <Check size={14} /> See funding risks and missing information
            </li>
            <li>
              <Check size={14} /> Every score comes with an explanation
            </li>
          </ul>
          <Link className="text-link" to="/profile">
            Set up your profile <ArrowRight size={16} />
          </Link>
          <span className="panel-footnote">
            Last library update:{' '}
            {data?.items[0] ? formatDate(data.items[0].updated_at) : 'No records yet'}
          </span>
        </section>
      </div>
    </div>
  )
}
