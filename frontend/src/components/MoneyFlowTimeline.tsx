import type { Transaction } from '../types'

interface MoneyFlowTimelineProps {
  transactions: Transaction[] | null
  citedTransactionIds: string[]
}

function money(value: number, currency: string) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${currency}`
}

function signedAmount(t: Transaction) {
  return t.direction === 'inbound' ? t.amount : -t.amount
}

function inferOpeningBalance(transactions: Transaction[]) {
  const first = transactions[0]
  if (!first) return 0
  return first.runningBalance - signedAmount(first)
}

function flowSummary(transactions: Transaction[]) {
  const inbound = transactions
    .filter((t) => t.direction === 'inbound')
    .reduce((sum, t) => sum + t.amount, 0)
  const outbound = transactions
    .filter((t) => t.direction === 'outbound')
    .reduce((sum, t) => sum + t.amount, 0)
  const openingBalance = inferOpeningBalance(transactions)
  const endingBalance = transactions.at(-1)?.runningBalance ?? openingBalance
  const currency = transactions[0]?.currency ?? 'MYR'
  const retained = inbound > 0 ? Math.max(0, Math.min(1, endingBalance / inbound)) : null
  return { inbound, outbound, openingBalance, endingBalance, currency, retained }
}

function timeLabel(timestamp: string) {
  return timestamp.substring(5, 16).replace('T', ' ')
}

export function MoneyFlowTimeline({ transactions, citedTransactionIds }: MoneyFlowTimelineProps) {
  if (!transactions?.length) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Money-flow timeline</h3>
        <p className="mt-2 text-[13px] text-ink-faint">No transactions loaded.</p>
      </section>
    )
  }

  const summary = flowSummary(transactions)
  const cited = new Set(citedTransactionIds)
  const maxAmount = Math.max(1, ...transactions.map((t) => t.amount))
  const maxBalance = Math.max(1, ...transactions.map((t) => t.runningBalance), summary.openingBalance)
  const drainRatio = summary.inbound > 0 ? summary.outbound / summary.inbound : 0
  const drainSignal = drainRatio >= 0.8 || summary.endingBalance < 1000

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="label">Money-flow timeline</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
            Funds movement compressed from the ledger: money in, money out, and retained balance.
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${
            drainSignal ? 'bg-escalate-soft text-escalate' : 'bg-verified-soft text-verified'
          }`}
        >
          {drainSignal ? 'Drain pattern visible' : 'Balance retained'}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <Metric label="Money in" value={money(summary.inbound, summary.currency)} tone="text-verified" />
        <Metric label="Money out" value={money(summary.outbound, summary.currency)} tone="text-escalate" />
        <Metric
          label="Ending balance"
          value={money(summary.endingBalance, summary.currency)}
          tone={drainSignal ? 'text-escalate' : 'text-ink'}
        />
      </div>

      <div className="mt-4 overflow-x-auto pb-1">
        <div className="relative flex min-w-max items-stretch gap-3">
          <div className="absolute top-[38px] right-0 left-0 h-px bg-line" />
          {transactions.map((t) => {
            const isInbound = t.direction === 'inbound'
            const isCited = cited.has(t.transactionId)
            const amountHeight = `${Math.max(18, (t.amount / maxAmount) * 58)}px`
            const balanceWidth = `${Math.max(3, (t.runningBalance / maxBalance) * 100)}%`
            return (
              <div
                key={t.transactionId}
                className={`relative w-36 shrink-0 rounded-md border bg-paper p-2 ${
                  isCited ? 'border-ink shadow-sm' : 'border-line'
                }`}
                title={`${t.transactionId} - ${t.counterpartyName}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-ink-faint">{timeLabel(t.timestamp)}</span>
                  {isCited && (
                    <span className="rounded bg-surface px-1 py-0.5 font-mono text-[9px] text-ink-faint">
                      cited
                    </span>
                  )}
                </div>
                <div className="mt-2 flex h-16 items-end justify-center">
                  <div
                    className={`w-8 rounded-t ${isInbound ? 'bg-verified' : 'bg-escalate'}`}
                    style={{ height: amountHeight }}
                  />
                </div>
                <div className="mt-2 flex items-baseline justify-between gap-2">
                  <span className={`text-[11px] font-semibold ${isInbound ? 'text-verified' : 'text-escalate'}`}>
                    {isInbound ? 'IN' : 'OUT'}
                  </span>
                  <span className="font-mono text-[11px] text-ink">{money(t.amount, t.currency)}</span>
                </div>
                <div className="mt-1 truncate text-[11px] text-ink-soft">{t.counterpartyName}</div>
                <div className="mt-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-ink-faint">balance</span>
                    <span
                      className={`font-mono text-[10px] tabular-nums ${
                        t.runningBalance < 1000 || t.flags.includes('balance-drain')
                          ? 'text-escalate'
                          : 'text-ink-faint'
                      }`}
                    >
                      {money(t.runningBalance, t.currency)}
                    </span>
                  </div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-line">
                    <div
                      className={`h-full rounded-full ${
                        t.runningBalance < 1000 || t.flags.includes('balance-drain') ? 'bg-escalate' : 'bg-ink/70'
                      }`}
                      style={{ width: balanceWidth }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-line pt-3 text-[11px] text-ink-faint">
        <span>
          Opening balance: <span className="font-mono text-ink-soft">{money(summary.openingBalance, summary.currency)}</span>
        </span>
        {summary.retained != null && (
          <span>
            Retained vs inflow:{' '}
            <span className={`font-mono ${drainSignal ? 'text-escalate' : 'text-ink-soft'}`}>
              {Math.round(summary.retained * 100)}%
            </span>
          </span>
        )}
      </div>
    </section>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-md border border-line bg-paper px-3 py-2">
      <div className="label">{label}</div>
      <div className={`mt-1 font-mono text-[14px] font-semibold tabular-nums ${tone}`}>{value}</div>
    </div>
  )
}
