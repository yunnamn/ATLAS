import { render, screen, renderHook, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ResearchState } from './pages/ResearchAgent'
import { useResearchRun } from './research'

it('distinguishes source support, contradiction, and unknown without implying human verification', () => {
  render(
    <>
      <ResearchState state="source_supported" />
      <ResearchState state="contradictory" />
      <ResearchState state="unknown" />
    </>,
  )
  expect(screen.getByText('Source-supported')).toBeVisible()
  expect(screen.getByText('Conflicting')).toBeVisible()
  expect(screen.getByText('Unknown')).toBeVisible()
  expect(screen.queryByText('Verified')).toBeNull()
})

it('loads a persisted terminal run, evidence, and report without starting another investigation', async () => {
  const fetcher = vi.fn(async (url: string) => {
    const data = url.endsWith('/report')
      ? { outcome: 'partial' }
      : url.endsWith('/evidence')
        ? { claims: [] }
        : { status: 'completed', steps: [{ id: 'step-1' }] }
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetcher)
  const finished = vi.fn()
  const { result } = renderHook(() => useResearchRun('persisted-run', finished))
  await waitFor(() => expect(result.current.report?.outcome).toBe('partial'))
  expect(result.current.evidence?.claims).toEqual([])
  expect(finished).toHaveBeenCalledTimes(1)
  expect(fetcher).toHaveBeenCalledTimes(3)
  expect(
    fetcher.mock.calls.every((call) => call[0].startsWith('/api/research/runs/persisted-run')),
  ).toBe(true)
})
