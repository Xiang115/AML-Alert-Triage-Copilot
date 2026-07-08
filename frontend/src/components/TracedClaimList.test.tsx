import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TracedClaimList } from './TracedClaimList'

describe('TracedClaimList', () => {
  it('renders evidence chips for an anchored claim and a warning for an unanchored one', () => {
    render(
      <TracedClaimList
        claims={[
          { text: 'GBP 47k in from 6 senders', anchored: true,
            evidence: { transactionIds: ['T-1', 'T-2'], firedIndicators: ['fan-in'] } },
          { text: 'No commercial rationale on file', anchored: false,
            evidence: { transactionIds: [], firedIndicators: [] } },
        ]}
      />,
    )
    expect(screen.getByText('GBP 47k in from 6 senders')).toBeTruthy()
    expect(screen.getByText('T-1')).toBeTruthy()
    expect(screen.getByText(/model judgment/i)).toBeTruthy()
  })

  it('shows a Remove control per claim only when onRemove is provided (STR editor mode)', () => {
    const onRemove = vi.fn()
    render(
      <TracedClaimList
        onRemove={onRemove}
        claims={[{ text: 'g1', anchored: true, evidence: { transactionIds: ['T-1'], firedIndicators: [] } }]}
      />,
    )
    screen.getByLabelText('Remove ground').click()
    expect(onRemove).toHaveBeenCalledWith(0)
  })
})
