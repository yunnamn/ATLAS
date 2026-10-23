import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api, deadlineDays, factValue, formatDate, useResource } from './api'

function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('API boundary', () => {
  it('returns backend data and preserves the method/body', async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ revision: 2 }))
    vi.stubGlobal('fetch', fetcher)
    expect(await api('/profile', { method: 'PUT', body: '{"name":"Researcher"}' })).toEqual({
      revision: 2,
    })
    expect(fetcher).toHaveBeenCalledWith(
      '/api/profile',
      expect.objectContaining({ method: 'PUT', body: '{"name":"Researcher"}' }),
    )
  })
  it('surfaces validation failures and non-JSON proxy errors', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response({ detail: 'Source missing' }, 422))
      .mockResolvedValueOnce(new Response('Bad gateway', { status: 502 }))
    vi.stubGlobal('fetch', fetcher)
    await expect(api('/imports')).rejects.toThrow('Source missing')
    await expect(api('/health')).rejects.toThrow('502')
  })
  it('does not set JSON content type on a file upload', async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ facts: {} }))
    vi.stubGlobal('fetch', fetcher)
    await api('/extract/pdf', { method: 'POST', body: new FormData() })
    expect(fetcher.mock.calls[0][1].headers).toEqual({})
  })
  it('discards an earlier query when a newer result arrives', async () => {
    let resolveOld!: (r: Response) => void
    const old = new Promise<Response>((resolve) => {
      resolveOld = resolve
    })
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockReturnValueOnce(old)
        .mockResolvedValueOnce(response({ title: 'new query' })),
    )
    const { result, rerender } = renderHook(({ path }) => useResource<{ title: string }>(path), {
      initialProps: { path: '/old' },
    })
    rerender({ path: '/new' })
    await waitFor(() => expect(result.current.data?.title).toBe('new query'))
    await act(async () => {
      resolveOld(response({ title: 'stale query' }))
      await old
    })
    expect(result.current.data?.title).toBe('new query')
  })
})

describe('presentation of uncertainty', () => {
  it('keeps unknown data explicit', () => {
    expect(factValue(null)).toBe('Unknown')
    expect(formatDate(null)).toBe('Not recorded')
  })
  it('counts date-only deadlines by UTC calendar day', () => {
    expect(deadlineDays('2027-01-15', new Date('2027-01-14T23:59:00Z'))).toBe(1)
    expect(deadlineDays('2027-01-15', new Date('2027-01-16T00:01:00Z'))).toBe(-1)
    expect(deadlineDays(null)).toBeNull()
    expect(formatDate('2027-01-15')).toBe('Jan 15, 2027')
  })
})
