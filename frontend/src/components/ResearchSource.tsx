import { ChevronDown, ExternalLink, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { formatDate, useResource } from '../api'
import type { ResearchDocument, ResearchSnippet } from '../research'
import { ErrorBox, Loading } from './ui'

export function SavedSource({
  runId,
  document,
  excerpt,
  close,
}: {
  runId: string
  document: ResearchDocument
  excerpt?: ResearchSnippet
  close: () => void
}) {
  const { data, error } = useResource<{ text: string }>(
    `/research/runs/${runId}/documents/${document.id}`,
  )
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  return (
    <dialog
      ref={dialog}
      className="research-source-dialog"
      aria-label="Saved source inspector"
      onCancel={close}
    >
      <section className="panel research-inspector" aria-label="Saved source inspector">
        <div className="section-heading">
          <div>
            <div className="eyebrow">
              SAVED EVIDENCE · {document.synthetic ? 'SYNTHETIC' : 'IMPORTED SOURCE'}
            </div>
            <h3>{document.title}</h3>
          </div>
          <button className="icon-btn" aria-label="Close source inspector" onClick={close}>
            <X size={19} />
          </button>
        </div>
        <p className="research-url">{document.url}</p>
        <p className="muted">
          Retrieved {formatDate(document.fetched_at)} · Last network verification{' '}
          {formatDate(document.last_checked_at)}
          {document.synthetic && ' · Fixture timestamps, no network request'}
        </p>
        <code className="source-hash">SHA-256 {document.sha256}</code>
        {excerpt && (
          <div className="selected-excerpt">
            <strong>
              {excerpt.purpose === 'scope' ? 'Program / intake scope' : 'Supporting excerpt'}
            </strong>
            <blockquote>{excerpt.quote}</blockquote>
            <small>
              Characters {excerpt.start}–{excerpt.end}
              {excerpt.location.page ? ` · PDF page ${excerpt.location.page}` : ''} · Exact span in
              normalized source text
            </small>
          </div>
        )}
        {error ? (
          <ErrorBox error={error} />
        ) : data ? (
          <details>
            <summary>
              Inspect full saved text <ChevronDown size={14} />
            </summary>
            <pre>{data.text}</pre>
          </details>
        ) : (
          <Loading />
        )}
        {!document.synthetic && (
          <a href={document.url} target="_blank" rel="noreferrer" className="text-link">
            Open original source <ExternalLink size={13} />
          </a>
        )}
      </section>
    </dialog>
  )
}
