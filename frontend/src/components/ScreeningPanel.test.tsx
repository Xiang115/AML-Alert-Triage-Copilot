import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ScreeningPanel } from './ScreeningPanel'
import type { Screening } from '../types'

const hit: Screening = {
  status: 'hit',
  blocked: true,
  screenedCounterparties: 6,
  matches: [
    { counterpartyId: 'CP-777', listName: 'OFAC SDN', matchedName: 'GLOBAL HORIZON TRADING LLC',
      matchType: 'exact', score: 1.0, program: 'SDGT' },
  ],
  citation: 'OFAC SDN sample',
}

const clear: Screening = {
  status: 'clear',
  blocked: false,
  screenedCounterparties: 11,
  matches: [],
  citation: 'OFAC SDN sample',
}

describe('ScreeningPanel', () => {
  it('renders the match, list, and the fail-safe review message when blocked', () => {
    render(<ScreeningPanel data={hit} />)
    expect(screen.getByText(/match — review required/i)).toBeTruthy()
    expect(screen.getByText(/GLOBAL HORIZON TRADING LLC/)).toBeTruthy()
    expect(screen.getByText(/will not auto-clear/i)).toBeTruthy()
    expect(screen.getByText(/deterministic screening runs outside the LLM and overrides routing/i)).toBeTruthy()
    expect(screen.getByText(/Even if triage recommends dismiss/i)).toBeTruthy()
    expect(screen.getByText(/screened 6 counterparties/i)).toBeTruthy()
  })

  it('shows the honest no-match positive signal when clear', () => {
    render(<ScreeningPanel data={clear} />)
    expect(screen.getByText(/^clear$/i)).toBeTruthy()
    expect(screen.getByText(/no watchlist matches/i)).toBeTruthy()
    expect(screen.getByText(/screened 11 counterparties/i)).toBeTruthy()
    expect(screen.getByText(/a future hit would override auto-clear/i)).toBeTruthy()
    expect(screen.queryByText(/will not auto-clear/i)).toBeNull()
  })

  it('renders nothing for an unscreened (pre-Slice-B) record', () => {
    const { container } = render(<ScreeningPanel data={null} />)
    expect(container.firstChild).toBeNull()
  })
})
