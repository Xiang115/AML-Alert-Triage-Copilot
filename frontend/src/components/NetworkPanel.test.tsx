import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NetworkPanel } from './NetworkPanel'
import type { MuleNetwork } from '../types'

const network: MuleNetwork = {
  seedAlertId: 'IBM-MULE-01',
  typology: { code: 'FI-01', name: 'Fan-in consolidation', source: 'FATF/BNM typology' },
  nodes: [
    { accountId: 'HUB', holderName: 'Sole Proprietorship #110823', role: 'hub', isSeed: false, x: 620, y: 260, totalLegs: 69, launderingLegs: 15 },
    { accountId: 'M1', holderName: 'Corporation #111314', role: 'mule', isSeed: false, x: 180, y: 120, totalLegs: 63, launderingLegs: 3 },
    { accountId: 'HM', holderName: 'Sole Proprietorship #110792', role: 'hidden_mule', isSeed: true, x: 180, y: 260, totalLegs: 290, launderingLegs: 5, note: 'looks normal alone' },
    { accountId: 'B1', holderName: 'Sole Proprietorship #30365', role: 'benign_cleared', isSeed: false, x: 180, y: 400, totalLegs: 97, launderingLegs: 0 },
  ],
  edges: [
    { fromAccountId: 'M1', toAccountId: 'HUB', amount: 1409306, currency: 'Ruble', transferCount: 1, laundering: true },
    { fromAccountId: 'HM', toAccountId: 'HUB', amount: 398277, currency: 'Ruble', transferCount: 1, laundering: true },
    { fromAccountId: 'B1', toAccountId: 'HUB', amount: 4047360, currency: 'Ruble', transferCount: 32, laundering: false },
  ],
  narrative: 'Accounts funnel into the hub; a hidden mule is re-surfaced while a legitimate payer is cleared.',
  source: 'Real IBM AMLworld HI-Medium cluster — illustrative; the measured numbers are the SAML-D triage metrics.',
  generatedAt: '2026-07-04T18:00:00+08:00',
}

describe('NetworkPanel', () => {
  it('renders every account with its holder name and role', () => {
    render(<NetworkPanel network={network} />)
    expect(screen.getByText('Sole Proprietorship #110792')).toBeTruthy()  // the hidden mule
    expect(screen.getByText('Sole Proprietorship #30365')).toBeTruthy()   // the cleared payer
    expect(screen.getByText(/Hidden mule/)).toBeTruthy()
    expect(screen.getByText(/Cleared — legitimate/)).toBeTruthy()
  })

  it('shows the narrative and the honesty caption (ADR-0015)', () => {
    render(<NetworkPanel network={network} />)
    expect(screen.getByText(network.narrative)).toBeTruthy()
    expect(screen.getByText(/illustrative.*SAML-D/i)).toBeTruthy()
  })

  it('explains the recall defense and measured-vs-illustrative boundary', () => {
    render(<NetworkPanel network={network} />)
    expect(screen.getByText(/Recall defense/i)).toBeTruthy()
    expect(screen.getByText(/Single-alert triage has a recall ceiling/i)).toBeTruthy()
    expect(screen.getAllByText(/1 hidden mule/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/1 benign neighbour/i)).toBeTruthy()
    expect(screen.getByText(/headline measured numbers remain the held-out SAML-D triage metrics/i)).toBeTruthy()
  })
})
