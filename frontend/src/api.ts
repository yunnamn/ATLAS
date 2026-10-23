import { useEffect, useState } from 'react'

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options?.headers,
    },
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* A proxy may return a non-JSON error. */
    }
    throw new Error(message)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export function useResource<T>(path: string, revision = 0) {
  const key = `${path}:${revision}`
  const [result, setResult] = useState<{ key: string; data?: T; error?: string; loading: boolean }>(
    { key: '', loading: true },
  )
  useEffect(() => {
    const controller = new AbortController()
    api<T>(path, { signal: controller.signal }).then(
      (data) => {
        if (!controller.signal.aborted) setResult({ key, data, loading: false })
      },
      (error) => {
        if (!controller.signal.aborted)
          setResult({ key, error: String(error.message), loading: false })
      },
    )
    return () => controller.abort()
  }, [path, revision, key])
  return result.key === key ? result : { loading: true, data: undefined, error: undefined }
}

export const labels: Record<string, string> = {
  funding: 'Funding coverage',
  tuition: 'Tuition coverage',
  stipend: 'Living stipend',
  travel: 'Travel support',
  insurance: 'Health insurance',
  application_fee: 'Application fee',
  proof_of_funds: 'Proof of funds',
  return_obligation: 'Return obligation',
  deadline: 'Application deadline',
  language: 'Minimum IELTS',
  min_gpa: 'Minimum GPA (4.0)',
  eligible_nationalities: 'Eligible nationalities',
  required_degree: 'Required degree',
  application_url: 'Application URL',
  eligibility_conditions: 'Eligibility conditions',
  language_requirements: 'Language requirements',
  scholarship_obligations: 'Scholarship obligations',
}
export function factValue(value: string | null | undefined): string {
  if (!value) return 'Unknown'
  return (
    (
      {
        tuition_and_stipend: 'Tuition + living stipend',
        tuition_only: 'Tuition only',
        partial: 'Partial funding',
        none: 'No funding',
        bachelor: 'Bachelor’s degree',
        master: 'Master’s degree',
        all: 'All nationalities',
        yes: 'Yes',
        no: 'No',
      } as Record<string, string>
    )[value] ?? value
  )
}
export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not recorded'
  const date = new Date(value.length === 10 ? `${value}T12:00:00Z` : value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'UTC',
      }).format(date)
}
export function deadlineDays(value: string | null | undefined, now = new Date()): number | null {
  if (!value) return null
  // Date-only deadlines have no inferred timezone or closing hour.
  return Math.ceil(
    (Date.parse(`${value}T00:00:00Z`) -
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())) /
      86400000,
  )
}
