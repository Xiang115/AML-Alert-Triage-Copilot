import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { TransactionTable } from './TransactionTable'
import type { Transaction } from '../types'

function txn(overrides: Partial<Transaction>): Transaction {
  return {
    transactionId: 'T-0',
    timestamp: '2026-06-14T09:00:00',
    amount: 1000,
    currency: 'MYR',
    direction: 'inbound',
    counterpartyName: 'Acme Ltd',
    channel: 'transfer',
    runningBalance: 5000,
    flags: [],
    ...overrides,
  }
}

describe('TransactionTable', () => {
  it('highlights only the cited transaction rows', () => {
    const transactions = [
      txn({ transactionId: 'T-1', runningBalance: 50100 }),
      txn({ transactionId: 'T-2', runningBalance: 49000 }),
    ]
    const { container } = render(
      <TransactionTable transactions={transactions} citedTransactionIds={['T-1']} />,
    )
    const rows = container.querySelectorAll('tbody tr')
    expect(rows[0].className).toContain('border-l-ink') // cited
    expect(rows[1].className).not.toContain('border-l-ink') // not cited
    expect(rows[1].className).toContain('border-l-transparent')
  })

  it('renders the running-balance draining style when the balance is low', () => {
    const transactions = [
      txn({ transactionId: 'T-1', runningBalance: 50100 }),
      txn({ transactionId: 'T-2', runningBalance: 300 }), // drained below 1000
    ]
    const { container } = render(
      <TransactionTable transactions={transactions} citedTransactionIds={[]} />,
    )
    const balanceSpans = container.querySelectorAll('tbody tr td:last-child > span')
    expect(balanceSpans[0].className).not.toContain('text-escalate') // healthy balance
    expect(balanceSpans[1].className).toContain('text-escalate') // draining
  })

  it('shows an empty-state row when there are no transactions', () => {
    const { container } = render(
      <TransactionTable transactions={null} citedTransactionIds={[]} />,
    )
    expect(container.textContent).toContain('No transactions loaded.')
  })
})
