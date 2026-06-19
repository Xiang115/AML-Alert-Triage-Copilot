import type { Transaction } from '../types'

interface TransactionTableProps {
  transactions: Transaction[] | null
  citedTransactionIds: string[]
}

export function TransactionTable({ transactions, citedTransactionIds }: TransactionTableProps) {
  return (
    <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-2.5">
      <h3 className="text-2xs font-black uppercase tracking-wider text-slate-500">Transaction History</h3>
      <div className="overflow-hidden rounded-lg border border-slate-900 bg-slate-950/40">
        <table className="w-full text-left text-3xs">
          <thead className="bg-slate-950 border-b border-slate-900 text-slate-500 font-bold uppercase tracking-wider">
            <tr>
              <th className="px-2.5 py-2">ID / Time</th>
              <th className="px-2.5 py-2">Direction</th>
              <th className="px-2.5 py-2">Counterparty</th>
              <th className="px-2.5 py-2 text-right">Amount</th>
              <th className="px-2.5 py-2 text-right">Running Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-900/50">
            {transactions?.map((t) => {
              const isCited = citedTransactionIds.includes(t.transactionId)
              const isDraining = t.flags.includes('balance-drain') || t.runningBalance < 1000

              return (
                <tr
                  key={t.transactionId}
                  className={`transition-colors duration-150 relative ${
                    isCited
                      ? 'border-l-2 border-teal-500/80 bg-slate-900/30'
                      : 'border-l-2 border-transparent hover:bg-slate-900/20'
                  }`}
                >
                  <td className="px-2.5 py-2.5 font-mono">
                    <div className="font-semibold text-slate-300">{t.transactionId}</div>
                    <div className="text-3xs text-slate-600 mt-0.5">{t.timestamp.substring(0, 16).replace('T', ' ')}</div>
                  </td>
                  <td className="px-2.5 py-2.5">
                    <span className={`text-3xs font-extrabold uppercase tracking-wide ${
                      t.direction === 'inbound'
                        ? 'text-emerald-400/90'
                        : 'text-rose-400/90'
                    }`}>
                      {t.direction}
                    </span>
                  </td>
                  <td className="px-2.5 py-2.5">
                    <div className="font-semibold text-slate-400">{t.counterpartyName}</div>
                    <div className="text-3xs text-slate-650 font-mono">{t.channel}</div>
                  </td>
                  <td className="px-2.5 py-2.5 text-right font-mono font-bold text-slate-300">
                    {t.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} {t.currency}
                  </td>
                  <td className="px-2.5 py-2.5 text-right font-mono text-slate-400">
                    <span className={isDraining ? 'text-rose-450 font-bold' : ''}>
                      {t.runningBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })} {t.currency}
                    </span>
                  </td>
                </tr>
              )
            }) ?? (
              <tr>
                <td colSpan={5} className="text-center py-4 text-slate-600 text-3xs">No transactions loaded.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
