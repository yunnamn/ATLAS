import { ArrowLeftRight, Plus, Search, SlidersHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { factValue, formatDate, useResource } from '../api'
import { Empty, ErrorBox, Loading, OpportunityCard, StateBadge } from '../components/ui'
import { useWorkspace } from '../components/workspace'
import type { Directory as DirectoryData } from '../types'

export function Directory() {
  const { revision, openImport } = useWorkspace()
  const [params, setParams] = useSearchParams()
  const [selected, setSelected] = useState<number[]>([])
  const [comparing, setComparing] = useState(false)
  const { data, error, loading } = useResource<DirectoryData>(
    `/opportunities?${params.toString()}&limit=100`,
    revision,
  )
  const all = useResource<DirectoryData>('/opportunities?limit=100', revision)
  const compareItems = all.data?.items.filter((o) => selected.includes(o.id)) ?? []
  function filter(key: string, value: string) {
    // Router transitions may lag rapid input events; history already has the latest filters.
    const next = new URLSearchParams(window.location.search)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('offset')
    setParams(next, { replace: true })
  }
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">RESEARCH WITH INTENTION</div>
          <h1>Discover your next chapter.</h1>
          <p>Explore opportunities. Inspect the evidence. Find what fits your ambitions.</p>
        </div>
        <button className="btn primary" onClick={openImport}>
          <Plus size={16} />
          Add research
        </button>
      </div>
      <div className="directory-notice">
        <span className="status-dot" />
        <strong>Evidence-first discovery</strong>
        <span>
          Synthetic examples are labeled. Listed funding is a recorded claim, not a verified
          guarantee.
        </span>
      </div>
      <div className="filter-bar">
        <label className="search-field">
          <Search size={18} />
          <input
            aria-label="Search directory"
            placeholder="Search programs, subjects, institutions…"
            value={params.get('q') ?? ''}
            onChange={(e) => filter('q', e.target.value)}
          />
        </label>
        <label className="select-field">
          <span>Destination</span>
          <select
            aria-label="Filter by destination"
            value={params.get('country') ?? ''}
            onChange={(e) => filter('country', e.target.value)}
          >
            <option value="">All destinations</option>
            {(all.data?.countries ?? []).map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span>Funding</span>
          <select
            aria-label="Filter by funding"
            value={params.get('funding') ?? ''}
            onChange={(e) => filter('funding', e.target.value)}
          >
            <option value="">All funding types</option>
            <option value="tuition_and_stipend">Tuition + living</option>
            <option value="tuition_only">Tuition only</option>
            <option value="partial">Partial funding</option>
            <option value="none">No funding</option>
          </select>
        </label>
      </div>
      <div className="directory-toolbar">
        <span>
          <strong>{data?.total ?? '…'}</strong> opportunities
          {params.size > 0 && (
            <button className="clear-button" onClick={() => setParams({})}>
              Clear filters <X size={12} />
            </button>
          )}
        </span>
        <label>
          <SlidersHorizontal size={14} />
          <input
            type="checkbox"
            checked={params.get('review') === 'true'}
            onChange={(e) => filter('review', e.target.checked ? 'true' : '')}
          />
          Needs evidence review
        </label>
      </div>
      {error ? (
        <ErrorBox error={error} />
      ) : loading ? (
        <Loading />
      ) : data?.items.length ? (
        <div className="cards-grid directory-cards">
          {data.items.map((o) => (
            <OpportunityCard
              key={o.id}
              opportunity={o}
              selected={selected.includes(o.id)}
              onCompare={() =>
                setSelected((ids) =>
                  ids.includes(o.id)
                    ? ids.filter((i) => i !== o.id)
                    : ids.length < 3
                      ? [...ids, o.id]
                      : ids,
                )
              }
            />
          ))}
        </div>
      ) : (
        <Empty
          title="No opportunities found."
          text={
            params.size
              ? 'Try a broader search or clear your filters.'
              : 'Your research library is empty. Add your first record or explore the synthetic collection.'
          }
          action={!params.size}
        />
      )}
      {selected.length > 0 && (
        <div className="compare-bar">
          <span>
            <ArrowLeftRight size={18} />
            {selected.length} of 3 selected
          </span>
          <button
            className="btn primary"
            disabled={selected.length < 2}
            onClick={() => setComparing(!comparing)}
          >
            {comparing ? 'Hide comparison' : 'Compare opportunities'}
          </button>
          <button
            className="icon-btn"
            aria-label="Clear comparison"
            onClick={() => {
              setSelected([])
              setComparing(false)
            }}
          >
            <X size={18} />
          </button>
        </div>
      )}
      {comparing && (
        <section className="panel comparison">
          <h2>A closer look, side by side.</h2>
          <p className="muted">
            Compare recorded claims. Each fact retains its own verification state.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Research field</th>
                  {compareItems.map((o) => (
                    <th key={o.id}>
                      <Link to={`/opportunities/${o.id}`}>{o.title}</Link>
                      {o.synthetic && <small>Synthetic demo</small>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  'country',
                  'funding',
                  'deadline',
                  'application_fee',
                  'proof_of_funds',
                  'return_obligation',
                  'language',
                  'min_gpa',
                ].map((key) => (
                  <tr key={key}>
                    <th>{key.replaceAll('_', ' ')}</th>
                    {compareItems.map((o) => (
                      <td key={o.id}>
                        {key === 'country' ? (
                          o.country
                        ) : (
                          <>
                            {key === 'deadline'
                              ? formatDate(o.facts[key]?.value)
                              : factValue(o.facts[key]?.value)}
                            <StateBadge state={o.facts[key]?.state ?? 'unknown'} />
                          </>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
