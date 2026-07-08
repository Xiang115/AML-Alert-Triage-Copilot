import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { GoamlDefense } from './GoamlDefense'

describe('GoamlDefense', () => {
  it('keeps filing locked before analyst sign-off', () => {
    render(
      <GoamlDefense
        canExport={false}
        ack={null}
        onExport={() => undefined}
        citedTransactionCount={3}
        anchoredClaimCount={2}
        totalClaimCount={2}
        pulledClaimCount={0}
      />,
    )

    expect(screen.getByText(/goAML filing defense/i)).toBeTruthy()
    expect(screen.getByText(/Approve this escalation before any STR can leave/i)).toBeTruthy()
    expect(screen.getByText(/no goAML XML can be exported without analyst approval/i)).toBeTruthy()
  })

  it('shows export validation and invokes export when unlocked', () => {
    const onExport = vi.fn()

    render(
      <GoamlDefense
        canExport
        ack={null}
        onExport={onExport}
        citedTransactionCount={4}
        anchoredClaimCount={3}
        totalClaimCount={3}
        pulledClaimCount={0}
      />,
    )

    expect(screen.getByText(/blocks unanchored grounds/i)).toBeTruthy()
    expect(screen.getByText(/validates it against the checked-in XSD/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Export & file goAML STR/i }))
    expect(onExport).toHaveBeenCalledTimes(1)
  })

  it('shows FIU acknowledgement and audit recording after submission', () => {
    render(
      <GoamlDefense
        canExport
        ack={{
          alertId: 'A-1',
          submissionRef: 'MYFIU-2026-000123',
          status: 'accepted',
          submittedAt: '2026-07-06T10:00:00+08:00',
        }}
        onExport={() => undefined}
        citedTransactionCount={4}
        anchoredClaimCount={3}
        totalClaimCount={3}
        pulledClaimCount={0}
      />,
    )

    expect(screen.getByText(/Filed to goAML/i)).toBeTruthy()
    expect(screen.getAllByText(/MYFIU-2026-000123/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/submission event recorded to audit/i)).toBeTruthy()
  })
})
