import { createContext, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, useResource } from '../api'
import type { Application } from '../types'

interface Workspace {
  revision: number
  refresh: () => void
  saved: Set<number>
  applications: Application[]
  applicationsLoading: boolean
  applicationsError?: string
  toggleSave: (id: number) => Promise<void>
  pending: number | null
  openImport: () => void
  importOpen: boolean
  closeImport: () => void
  seed: () => Promise<void>
  busy: boolean
  notify: (message: string, error?: boolean) => void
}
const Context = createContext<Workspace | null>(null)
export function useWorkspace() {
  const context = useContext(Context)
  if (!context) throw Error('Missing workspace')
  return context
}
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [revision, setRevision] = useState(0)
  const [pending, setPending] = useState<number | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error: boolean; id: number } | null>(null)
  const apps = useResource<Application[]>('/applications', revision)
  const saved = useMemo(() => new Set(apps.data?.map((a) => a.opportunity_id) ?? []), [apps.data])
  function refresh() {
    setRevision((r) => r + 1)
  }
  function notify(message: string, error = false) {
    setToast({ message, error, id: Date.now() })
  }
  async function toggleSave(id: number) {
    if (pending !== null || apps.loading || apps.error) {
      if (apps.error) notify(apps.error, true)
      return
    }
    setPending(id)
    try {
      await api(`/applications/${id}`, {
        method: saved.has(id) ? 'DELETE' : 'PUT',
        ...(saved.has(id) ? {} : { body: JSON.stringify({ status: 'saved' }) }),
      })
      notify(saved.has(id) ? 'Removed from your shortlist.' : 'Added to your shortlist.')
      refresh()
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setPending(null)
    }
  }
  async function seed() {
    setBusy(true)
    try {
      const result = await api<{ created: number[]; skipped: number[] }>('/imports/demo', {
        method: 'POST',
      })
      notify(
        `${result.created.length} synthetic examples imported. ${result.skipped.length} existing records preserved.`,
      )
      refresh()
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Context.Provider
      value={{
        revision,
        refresh,
        saved,
        applications: apps.data ?? [],
        applicationsLoading: apps.loading,
        applicationsError: apps.error,
        toggleSave,
        pending,
        openImport: () => setImportOpen(true),
        importOpen,
        closeImport: () => setImportOpen(false),
        seed,
        busy,
        notify,
      }}
    >
      {children}
      {toast && (
        <div
          className={`toast ${toast.error ? 'toast-error' : ''}`}
          role={toast.error ? 'alert' : 'status'}
          key={toast.id}
        >
          <span>{toast.message}</span>
          <button aria-label="Dismiss notification" onClick={() => setToast(null)}>
            ×
          </button>
        </div>
      )}
    </Context.Provider>
  )
}
