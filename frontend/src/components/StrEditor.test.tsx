import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StrEditor } from './StrEditor'
import type { STRDraft, Transaction } from '../types'

const strDraft: STRDraft = {
  reportDate: '2026-07-09T00:00:00+08:00',
  reportingInstitution: 'Demo Bank Bhd',
  subject: { accountId: '7881299162', holderName: 'SAML-D account 7881299162', accountType: 'unknown', openedAt: '2024-01-01T00:00:00+08:00' },
  typology: { code: 'PT-01', name: 'Pass-through / rapid movement', source: 'FATF' },
  period: { from: '2026-06-01T00:00:00+08:00', to: '2026-06-30T00:00:00+08:00' },
  activitySummary: 'Funds moved through the account within hours.',
  citedTransactions: [],
  groundsForSuspicion: ['Rapid pass-through of inbound funds.'],
  recommendedAction: 'File an STR.',
}

const citedTransactions: Transaction[] = [
  { transactionId: 'T-1', timestamp: '2026-06-02T09:00:00+08:00', amount: 9500, currency: 'MYR', direction: 'inbound', counterpartyName: 'Zephyr Holdings Ltd', channel: 'transfer', runningBalance: 9500, flags: [] },
  { transactionId: 'T-2', timestamp: '2026-06-02T11:00:00+08:00', amount: 9400, currency: 'MYR', direction: 'outbound', counterpartyName: 'Meridian Trading Sdn', channel: 'transfer', runningBalance: 100, flags: [] },
]

const noop = () => undefined

// The right-panel STR no longer repeats the cited legs as a table — the left-panel ledger
// (TransactionTable) already lists every transaction and highlights the cited ones. The STR keeps
// only the honest cited-count in the goAML evidence package, not a duplicate row-by-row table.
describe('StrEditor reported-transactions duplication', () => {
  it('does not render a Reported-transactions table (the ledger already shows the legs)', () => {
    render(
      <StrEditor
        strDraft={strDraft}
        citedTransactions={citedTransactions}
        summary={strDraft.activitySummary}
        onSummaryChange={noop}
        grounds={strDraft.groundsForSuspicion}
        onAddGround={noop}
        onRemoveGround={noop}
        canExport={false}
        onExport={noop}
        ack={null}
      />,
    )

    expect(screen.queryByText(/reported transactions/i)).toBeNull()
    // The per-leg detail that lived only in that table is gone from the STR panel.
    expect(screen.queryByText('Zephyr Holdings Ltd')).toBeNull()
    expect(screen.queryByText('Meridian Trading Sdn')).toBeNull()
  })

  it('still cites the transaction count in the goAML evidence package', () => {
    render(
      <StrEditor
        strDraft={strDraft}
        citedTransactions={citedTransactions}
        summary={strDraft.activitySummary}
        onSummaryChange={noop}
        grounds={strDraft.groundsForSuspicion}
        onAddGround={noop}
        onRemoveGround={noop}
        canExport={false}
        onExport={noop}
        ack={null}
      />,
    )

    expect(screen.getByText(/2 cited transaction\(s\)/i)).toBeTruthy()
  })
})
