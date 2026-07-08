import { useEffect, useRef } from 'react'
import type { Transaction } from '../types'

interface TransactionTableProps {
  transactions: Transaction[] | null
  citedTransactionIds: string[]
  // Set by the Evidence Register (ADR-0013): the transaction to scroll to and highlight.
  focusedTransactionId?: string | null
}

function amount(value: number, currency: string) {
  return `${value.toLocaleString(undefined, { minimumFractionDigits: 2 })} ${currency}`
}

export function TransactionTable({ transactions, citedTransactionIds, focusedTransactionId }: TransactionTableProps) {
  // Scale the balance bars to the largest balance so the drain-to-zero is legible.
  const maxBalance = Math.max(1, ...(transactions ?? []).map((t) => t.runningBalance))
  const focusedRef = useRef<HTMLTableRowElement | null>(null)
  useEffect(() => {
    if (focusedTransactionId && focusedRef.current) {
      focusedRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [focusedTransactionId])

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Transaction ledger</h3>
        {citedTransactionIds.length > 0 && (
          // Citation Grounding (CONTEXT.md): every cited id is a real ledger entry. Claims
          // provenance — that the transactions exist in the source — not that they prove guilt.
          <span className="inline-flex items-center gap-1 rounded-full bg-verified-soft px-2.5 py-1 text-[11px] font-medium text-verified">
            ✓ {citedTransactionIds.length} verified against source ledger
          </span>
        )}
      </div>

      <table className="mt-3 w-full text-left text-[12px]">
        <thead>
          <tr className="border-b border-line text-ink-faint">
            <th className="py-2 pr-3 font-medium">ID / Time</th>
            <th className="py-2 pr-3 font-medium">Direction</th>
            <th className="py-2 pr-3 font-medium">Counterparty</th>
            <th className="py-2 pr-3 text-right font-medium">Amount</th>
            <th className="py-2 text-right font-medium">Running balance</th>
          </tr>
        </thead>
        <tbody>
          {transactions?.map((t) => {
            const isCited = citedTransactionIds.includes(t.transactionId)
            const isFocused = t.transactionId === focusedTransactionId
            const isDraining = t.flags.includes('balance-drain') || t.runningBalance < 1000
            const barWidth = `${Math.max(2, (t.runningBalance / maxBalance) * 100)}%`

            return (
              <tr
                key={t.transactionId}
                ref={isFocused ? focusedRef : undefined}
                className={`border-b border-line border-l-2 align-top transition-colors ${
                  isFocused ? 'border-l-flag bg-flag-soft' : isCited ? 'border-l-ink bg-paper' : 'border-l-transparent'
                }`}
              >
                <td className="py-2.5 pr-3 pl-3 font-mono">
                  <div className="text-ink">{t.transactionId}</div>
                  <div className="mt-0.5 text-ink-faint">{t.timestamp.substring(0, 16).replace('T', ' ')}</div>
                </td>
                <td className="py-2.5 pr-3">
                  <span className={t.direction === 'inbound' ? 'text-verified' : 'text-ink-soft'}>
                    {t.direction}
                  </span>
                </td>
                <td className="py-2.5 pr-3">
                  <div className="text-ink">{t.counterpartyName}</div>
                  <div className="mt-0.5 font-mono text-ink-faint">{t.channel}</div>
                </td>
                <td className="py-2.5 pr-3 text-right font-mono tabular-nums text-ink">
                  {amount(t.amount, t.currency)}
                </td>
                <td className="py-2.5 text-right">
                  <span className={`font-mono tabular-nums ${isDraining ? 'text-escalate' : 'text-ink'}`}>
                    {amount(t.runningBalance, t.currency)}
                  </span>
                  <div className="mt-1 ml-auto h-1 w-24 overflow-hidden rounded-full bg-line">
                    <div
                      className={`h-full rounded-full ${isDraining ? 'bg-escalate' : 'bg-ink/70'}`}
                      style={{ width: barWidth }}
                    ></div>
                  </div>
                </td>
              </tr>
            )
          }) ?? (
            <tr>
              <td colSpan={5} className="py-4 text-center text-ink-faint">No transactions loaded.</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  )
}
