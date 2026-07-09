import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SuppressionPanel } from './SuppressionPanel'
import type { Suppression } from '../types'

const suppressed: Suppression = {
  status: 'suppressed',
  matchedPatternId: 'typ=FI-01|amt=3',
  sourceDecisionId: 'SD-00010',
  sourceAlertId: 'SD-00010',
  signature: 'typ=FI-01|amt=3',
  clearedCount: 1,
  clearedAt: '2026-07-01T09:14:00+08:00',
  rationale: 'A benign look-alike with the same behavioral envelope was cleared before.',
}

const revoked: Suppression = {
  ...suppressed,
  status: 'revoked',
  revokedNetworkId: 'IBM-MULE-01',
  rationale: 'Counterparty flagged as a mule-network consolidation hub. Suppression REVOKED.',
}

describe('SuppressionPanel', () => {
  it('says "auto-suppressed" only when the alert actually auto-cleared', () => {
    render(<SuppressionPanel data={suppressed} routing="autoCleared" />)
    expect(screen.getByText(/auto-suppressed/i)).toBeTruthy()
    expect(screen.getByText(/SD-00010/)).toBeTruthy()
  })

  it('does not claim auto-suppressed when another control holds it for review', () => {
    render(<SuppressionPanel data={suppressed} routing="needsReview" />)
    // The memory matched, but the alert is still routed to a human — must not overclaim.
    expect(screen.queryByText(/auto-suppressed/i)).toBeNull()
    expect(screen.getByText(/held for review/i)).toBeTruthy()
    expect(screen.getByText(/previously cleared pattern/i)).toBeTruthy()
  })

  it('renders the network-revocation alarm state', () => {
    render(<SuppressionPanel data={revoked} routing="needsReview" />)
    expect(screen.getByText(/suppression revoked — counterparty/i)).toBeTruthy()
    expect(screen.getByText(/IBM-MULE-01/)).toBeTruthy()
  })

  it('renders nothing without data', () => {
    const { container } = render(<SuppressionPanel data={null} />)
    expect(container.firstChild).toBeNull()
  })
})
