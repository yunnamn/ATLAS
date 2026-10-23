import { FileJson2, FileText, FlaskConical, Upload, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, labels } from '../api'
import { useWorkspace } from './workspace'
import type { Fact, Source } from '../types'

interface Extraction {
  source: Source
  facts: Record<string, Fact>
  warning: string
  characters: number
}
const skeleton = () => ({
  external_id: `research-${crypto.randomUUID().slice(0, 8)}`,
  title: '',
  institution: '',
  country: '',
  category: 'masters',
  summary: '',
  subjects: [],
  synthetic: false,
  sources: [],
  facts: {},
})
function ImportContent() {
  const { closeImport, refresh, notify, seed, busy: seeding } = useWorkspace()
  const dialog = useRef<HTMLDialogElement>(null)
  const [mode, setMode] = useState<'json' | 'document'>('json')
  const [json, setJson] = useState(JSON.stringify(skeleton(), null, 2))
  const [text, setText] = useState('')
  const [label, setLabel] = useState('Research notes')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [extraction, setExtraction] = useState<Extraction | null>(null)
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  async function importJSON(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const parsed = JSON.parse(json)
      const body = Array.isArray(parsed)
        ? { opportunities: parsed }
        : parsed.opportunities
          ? parsed
          : { opportunities: [parsed] }
      const result = await api<{ created: number[]; skipped: number[] }>('/imports', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      refresh()
      notify(
        `${result.created.length} records imported. ${result.skipped.length} existing records preserved.`,
      )
      closeImport()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function extract(file?: File) {
    setError('')
    setBusy(true)
    try {
      let result: Extraction
      if (file) {
        const body = new FormData()
        body.append('file', file)
        result = await api('/extract/pdf', { method: 'POST', body })
      } else {
        result = await api('/extract/text', {
          method: 'POST',
          body: JSON.stringify({ text, label }),
        })
      }
      setExtraction(result)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  function useCandidates() {
    setJson(
      JSON.stringify(
        { ...skeleton(), sources: [extraction?.source], facts: extraction?.facts },
        null,
        2,
      ),
    )
    setMode('json')
  }
  async function loadSample() {
    setBusy(true)
    setError('')
    try {
      const demo = await api<{ opportunities: unknown[] }>('/demo-records')
      setJson(JSON.stringify(demo.opportunities[0], null, 2))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <dialog
      ref={dialog}
      className="import-dialog"
      aria-labelledby="import-title"
      onCancel={closeImport}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const r = e.currentTarget.getBoundingClientRect()
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            closeImport()
        }
      }}
    >
      <div className="dialog-heading">
        <div>
          <div className="eyebrow">BRING YOUR OWN RESEARCH</div>
          <h2 id="import-title">From source to understanding.</h2>
        </div>
        <button className="icon-btn" aria-label="Close import" onClick={closeImport}>
          <X size={21} />
        </button>
      </div>
      <p className="muted">
        Import reviewed records or extract candidates from a local document. Nothing is fetched or
        sent to a model provider.
      </p>
      <div className="tabs">
        <button
          className={mode === 'json' ? 'selected' : ''}
          onClick={() => {
            setMode('json')
            setError('')
          }}
        >
          <FileJson2 size={16} />
          Structured JSON
        </button>
        <button
          className={mode === 'document' ? 'selected' : ''}
          onClick={() => {
            setMode('document')
            setError('')
          }}
        >
          <FileText size={16} />
          PDF / source text
        </button>
      </div>
      {mode === 'json' ? (
        <form onSubmit={importJSON}>
          <div className="import-help">
            <strong>A record, an array, or an opportunities batch.</strong>
            <p>
              Fill in title, institution, country, and summary. Facts need a value and state;
              unknown fields are filled automatically. Sources and excerpts stay attached to claims.
            </p>
            <button type="button" className="text-link" onClick={loadSample} disabled={busy}>
              Load one synthetic example
            </button>
          </div>
          <label>
            Opportunity JSON
            <textarea
              className="json-editor"
              spellCheck={false}
              value={json}
              onChange={(e) => setJson(e.target.value)}
              required
              maxLength={1_000_000}
            />
          </label>
          <p className="field-note">
            Existing external IDs are skipped to protect corrections. Website URLs are stored as
            citations and are not downloaded. This local workspace does not authenticate source
            ownership.
          </p>
          <div className="button-row">
            <button className="btn primary" disabled={busy}>
              <Upload size={15} />
              {busy ? 'Importing…' : 'Validate & import'}
            </button>
            <button type="button" className="btn secondary" onClick={closeImport}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="document-import">
          <label className="upload-zone">
            <Upload size={26} />
            <strong>{busy ? 'Reading document…' : 'Choose a local PDF'}</strong>
            <span>Text-based, unencrypted · up to 8 MiB / 30 pages</span>
            <input
              aria-label="Upload PDF"
              type="file"
              accept="application/pdf,.pdf"
              disabled={busy}
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  if (e.target.files[0].size > 8 * 1024 * 1024)
                    setError('Maximum PDF size is 8 MiB')
                  else void extract(e.target.files[0])
                }
              }}
            />
          </label>
          <div className="or-divider">or paste source text</div>
          <label>
            Source label
            <input
              value={label}
              maxLength={200}
              required
              onChange={(e) => setLabel(e.target.value)}
            />
          </label>
          <label>
            Source text
            <textarea
              value={text}
              maxLength={100_000}
              onChange={(e) => setText(e.target.value)}
              placeholder={
                'Deadline: 2027-01-15\nFunding: tuition_and_stipend\nMinimum GPA: 3.0\nIELTS: 6.5\nProof of funds: no\nReturn obligation: no'
              }
            />
          </label>
          <p className="field-note">
            The deterministic parser recognizes these exact English labels and funding codes only.
            It does not interpret arbitrary prose, convert currencies, or perform OCR. Duplicate or
            ambiguous labels are left unknown.
          </p>
          <button
            className="btn secondary"
            disabled={!text || !label || busy}
            onClick={() => extract()}
          >
            Extract candidates
          </button>
          {extraction && (
            <div className="extraction-result">
              <h3>{Object.keys(extraction.facts).length} candidate fields extracted</h3>
              <p>{extraction.warning}</p>
              {Object.entries(extraction.facts).map(([key, fact]) => (
                <div className="candidate-row" key={key}>
                  <strong>{labels[key]}</strong>
                  <span>{fact.value}</span>
                  <small>Unverified</small>
                </div>
              ))}
              <button className="btn primary" onClick={useCandidates}>
                Review record JSON
              </button>
              <small>Complete the program identity fields in JSON before importing.</small>
            </div>
          )}
        </div>
      )}
      {error && (
        <div className="inline-error import-error" role="alert">
          {error}
        </div>
      )}
      <div className="demo-import-footer">
        <FlaskConical size={18} />
        <span>Just exploring? Try the clearly labeled synthetic collection.</span>
        <button
          className="text-link"
          disabled={seeding}
          onClick={async () => {
            await seed()
          }}
        >
          Load all demo records
        </button>
      </div>
    </dialog>
  )
}
export function ImportDialog() {
  const { importOpen } = useWorkspace()
  return importOpen ? <ImportContent /> : null
}
