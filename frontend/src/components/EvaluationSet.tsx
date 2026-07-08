import { useEffect, useState } from 'react'
import { getEvaluation } from '../api'
import type { Evaluation } from '../types'

// The held-out evaluation SET made visible (GET /evaluation): every alert the accuracy number is
// measured on, with its ground-truth label — so the 250-alert measurement is inspectable, not
// hidden behind one percentage. The per-alert AI call is the deferred (a) path (one eval re-run).
export function EvaluationSet() {
  const [data, setData] = useState<Evaluation | null>(null)

  useEffect(() => {
    let active = true
    getEvaluation().then((e) => { if (active) setData(e) }).catch(() => {})
    return () => { active = false }
  }, [])

  if (!data) return null

  return (
    <div className="rounded-lg border border-line bg-surface p-6">
      <h3 className="text-[14px] font-semibold text-ink">Held-out evaluation set — {data.n} alerts</h3>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
        Every held-out alert the{' '}
        {data.accuracyVsLabels != null ? `${(data.accuracyVsLabels * 100).toFixed(0)}% accuracy` : 'metric'}{' '}
        is measured on, with its ground-truth label — {data.labelDistribution.escalate} report /{' '}
        {data.labelDistribution.dismiss} dismiss. The AI's per-alert call is the next step (one eval re-run).
      </p>

      <div className="mt-4 max-h-96 overflow-y-auto rounded-md border border-line">
        <table className="w-full border-collapse text-[12px]">
          <thead className="sticky top-0 bg-paper text-left text-ink-soft">
            <tr>
              <th className="px-3 py-2 font-medium">Alert</th>
              <th className="px-3 py-2 font-medium">Risk</th>
              <th className="px-3 py-2 font-medium">Txns</th>
              <th className="px-3 py-2 font-medium">Typology</th>
              <th className="px-3 py-2 font-medium">Ground truth</th>
            </tr>
          </thead>
          <tbody>
            {data.alerts.map((a) => (
              <tr key={a.alertId} className="border-t border-line">
                <td className="px-3 py-1.5 font-mono text-ink">{a.alertId}</td>
                <td className="px-3 py-1.5 tabular-nums text-ink-soft">{a.riskScore}</td>
                <td className="px-3 py-1.5 tabular-nums text-ink-soft">
                  {a.txnCount} <span className="text-ink-faint">({a.inCount}in/{a.outCount}out)</span>
                </td>
                <td className="px-3 py-1.5 text-ink-soft">
                  {a.coverageGap ? 'coverage gap' : (a.typology ?? '—')}
                </td>
                <td className="px-3 py-1.5">
                  <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                    a.label === 'escalate' ? 'bg-flag-soft text-flag' : 'bg-verified-soft text-verified'}`}>
                    {a.label === 'escalate' ? 'report' : 'dismiss'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
