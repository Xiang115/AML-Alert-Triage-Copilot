import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { MoneyFlowTimeline } from './MoneyFlowTimeline'
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

describe('MoneyFlowTimeline', () => {
  it('summarizes inbound, outbound, and ending balance', () => {
    const transactions = [
      txn({ transactionId: 'T-1', direction: 'inbound', amount: 10000, runningBalance: 11000 }),
      txn({ transactionId: 'T-2', direction: 'outbound', amount: 9300, runningBalance: 1700 }),
    ]

    const { container } = render(
      <MoneyFlowTimeline transactions={transactions} citedTransactionIds={[]} />,
    )

    expect(container.textContent).toContain('Money-flow timeline')
    expect(container.textContent).toContain('10,000 MYR')
    expect(container.textContent).toContain('9,300 MYR')
    expect(container.textContent).toContain('1,700 MYR')
  })

  it('marks a drain pattern when most inbound funds leave', () => {
    const transactions = [
      txn({ transactionId: 'T-1', direction: 'inbound', amount: 10000, runningBalance: 10000 }),
      txn({ transactionId: 'T-2', direction: 'outbound', amount: 9000, runningBalance: 1000 }),
    ]

    const { container } = render(
      <MoneyFlowTimeline transactions={transactions} citedTransactionIds={[]} />,
    )

    expect(container.textContent).toContain('Drain pattern visible')
    expect(container.textContent).toContain('Retained vs inflow:')
    expect(container.textContent).toContain('10%')
  })

  it('marks cited transactions in the timeline', () => {
    const transactions = [
      txn({ transactionId: 'T-1' }),
      txn({ transactionId: 'T-2', direction: 'outbound' }),
    ]

    const { container } = render(
      <MoneyFlowTimeline transactions={transactions} citedTransactionIds={['T-2']} />,
    )

    expect(container.textContent).toContain('cited')
  })

  it('renders an empty state when no transactions are available', () => {
    const { container } = render(
      <MoneyFlowTimeline transactions={null} citedTransactionIds={[]} />,
    )

    expect(container.textContent).toContain('No transactions loaded.')
  })
})
