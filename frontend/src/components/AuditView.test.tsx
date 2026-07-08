import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Hoisted mocks so the vi.mock factory can reference them safely.
const { getAudit, getAuditSummary } = vi.hoisted(() => ({
  getAudit: vi.fn(),
  getAuditSummary: vi.fn(),
}))
vi.mock('../api', () => ({ getAudit, getAuditSummary }))

import { AuditView } from './AuditView'

describe('AuditView session agreement strip', () => {
  beforeEach(() => {
    getAudit.mockReset()
    getAuditSummary.mockReset()
  })

  it('shows the agreement strip once analyst decisions exist', async () => {
    getAudit.mockResolvedValue([
      {
        alertId: 'DQ-001', event: 'decision', at: '2026-06-24T10:00:00', action: 'override',
        aiRecommendation: 'escalate', finalDisposition: 'dismiss', note: 'legit payroll run',
      },
    ])
    getAuditSummary.mockResolvedValue({ decisions: 3, approvals: 2, overrides: 1, agreementRate: 0.6667 })

    render(<AuditView />)
    expect(await screen.findByText('This session')).toBeTruthy()
    expect(await screen.findByText('67%')).toBeTruthy() // 0.6667 → 67%
    expect(screen.getByText(/Override is accountable/i)).toBeTruthy()
  })

  it('hides the strip when no analyst decisions have been made yet', async () => {
    getAudit.mockResolvedValue([
      { alertId: 'DQ-002', event: 'autoClear', at: '2026-06-23T06:00:00', aiRecommendation: 'dismiss', verifierStatus: 'agreed' },
    ])
    getAuditSummary.mockResolvedValue({ decisions: 0, approvals: 0, overrides: 0, agreementRate: null })

    render(<AuditView />)
    await screen.findByText('Auto-cleared') // wait for the load to settle
    expect(screen.queryByText('This session')).toBeNull()
    expect(screen.getByText(/dismiss-only, verifier-agreed, threshold-gated, and audit-recorded/i)).toBeTruthy()
  })

  it('shows submission acknowledgement as a defensible filing record', async () => {
    getAudit.mockResolvedValue([
      {
        alertId: 'DQ-003', event: 'submission', at: '2026-06-24T10:00:00',
        submissionRef: 'MYFIU-2026-000111',
      },
    ])
    getAuditSummary.mockResolvedValue({ decisions: 0, approvals: 0, overrides: 0, agreementRate: null })

    render(<AuditView />)

    expect(await screen.findByText('MYFIU-2026-000111')).toBeTruthy()
    expect(screen.getByText(/filing acknowledgement preserved/i)).toBeTruthy()
  })
})
