import {
  ArrowUpRight,
  BookOpen,
  Bot,
  Bookmark,
  CircleHelp,
  Compass,
  FileSearch,
  LayoutDashboard,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
} from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useWorkspace } from './workspace'
import { ImportDialog } from './ImportDialog'

const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/opportunities', label: 'Discover opportunities', icon: Compass },
  { to: '/research', label: 'Research agent', icon: Bot },
  { to: '/saved', label: 'My applications', icon: Bookmark },
  { to: '/sources', label: 'Sources & verification', icon: FileSearch },
]
export function Layout() {
  const { saved, openImport } = useWorkspace()
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const current =
    location.pathname === '/profile'
      ? 'Profile & preferences'
      : (nav.find((n) => n.to !== '/' && location.pathname.startsWith(n.to))?.label ?? 'Overview')
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <Compass size={33} strokeWidth={1.4} />
          <span>
            ATLAS<small>OPPORTUNITY INTELLIGENCE</small>
          </span>
        </NavLink>
        <div className="workspace-label">
          <span className="workspace-dot" /> Personal workspace{' '}
          <span className="local-tag">LOCAL</span>
        </div>
        <p className="nav-caption">YOUR WORKSPACE</p>
        <nav aria-label="Main navigation">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} />
              <span>{label}</span>
              {to === '/saved' && saved.size > 0 && <span className="nav-count">{saved.size}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <BookOpen size={19} />
            <strong>Go further, with clarity.</strong>
            <p>
              Good research opens doors.
              <br />
              Great evidence keeps them open.
            </p>
            <NavLink to="/sources">
              Explore your sources <ArrowUpRight size={13} />
            </NavLink>
          </div>
          <NavLink className="nav-item" to="/profile">
            <Settings2 size={18} />
            Profile & preferences
          </NavLink>
          <a
            className="nav-item"
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
          >
            <CircleHelp size={18} />
            Local API reference
            <ArrowUpRight size={13} />
          </a>
          <div className="sidebar-user">
            <span className="avatar">R</span>
            <div>
              <strong>Research workspace</strong>
              <small>Local · single user</small>
            </div>
            <span className="online-dot" />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>
            <strong>{current}</strong>
          </div>
          <form
            className="global-search"
            role="search"
            onSubmit={(e) => {
              e.preventDefault()
              navigate(`/opportunities?q=${encodeURIComponent(query)}`)
            }}
          >
            <Search size={16} />
            <input
              aria-label="Search all opportunities"
              placeholder="Find your next opportunity…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <kbd>↵</kbd>
          </form>
          <NavLink
            to="/profile"
            className="icon-btn mobile-profile-link"
            aria-label="Profile & preferences"
          >
            <Settings2 size={18} />
          </NavLink>
          <button className="btn primary btn-small" onClick={openImport}>
            <Plus size={15} />
            Import source
          </button>
        </header>
        <main id="main-content">
          <Outlet />
        </main>
        <footer>
          <span>
            <ShieldCheck size={13} /> Built for informed decisions.
          </span>
          <span>
            ATLAS <span className="footer-dot">·</span> Independent research, thoughtfully
            organized.
          </span>
        </footer>
      </div>
      <ImportDialog />
    </div>
  )
}
