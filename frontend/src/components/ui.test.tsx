import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Opportunity } from '../types'
import { OpportunityCard, StateBadge } from './ui'

const toggleSave = vi.fn()
vi.mock('./workspace', () => ({
  useWorkspace: () => ({ saved: new Set(), pending: null, toggleSave }),
}))
const record = {
  id: 7,
  institution: 'Synthetic Institute',
  title: 'Example master’s research',
  country: 'Sweden',
  summary: '<script>alert("untrusted")</script> This is a demonstration.',
  subjects: ['Research'],
  synthetic: true,
  facts: {
    funding: { value: null, state: 'unknown' },
    deadline: { value: null, state: 'unknown' },
  },
} as unknown as Opportunity

describe('opportunity presentation', () => {
  it('labels synthetic records and unknown benefits, links the actual detail route', () => {
    render(
      <MemoryRouter>
        <OpportunityCard opportunity={record} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Synthetic demo')).toBeInTheDocument()
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: record.title })).toHaveAttribute(
      'href',
      '/opportunities/7',
    )
    expect(document.querySelector('script')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: `Save ${record.title}` }))
    expect(toggleSave).toHaveBeenCalledWith(7)
  })
  it('distinguishes human review from unknown and unverified claims', () => {
    render(
      <>
        <StateBadge state="unknown" />
        <StateBadge state="unverified" />
        <StateBadge state="verified" />
      </>,
    )
    expect(screen.getByText('Unknown')).toBeVisible()
    expect(screen.getByText('Unverified')).toBeVisible()
    expect(screen.getByText('Reviewed · evidence linked')).toBeVisible()
  })
})
