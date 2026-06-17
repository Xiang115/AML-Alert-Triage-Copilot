import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getAlerts } from './api'
import type { Alert, AlertStatus } from './types'

const FILTERS: Array<{ label: string; value?: AlertStatus }> = [
  { label: 'All' },
  { label: 'Pending', value: 'pending' },
  { label: 'Approved', value: 'approved' },
  { label: 'Overridden', value: 'overridden' },
]

function Badge({ children, tone }: { children: ReactNode; tone: string }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${tone}`}>{children}</span>
}

function AlertCard({ alert }: { alert: Alert }) {
  const t = alert.triage
  const escalate = t.recommendation === 'escalate'
  const flagged = t.verifier.status === 'flagged'
  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-mono text-xs text-slate-400">{alert.alertId}</div>
          <div className="font-semibold text-slate-800">{alert.account.holderName}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-400">risk</div>
          <div className="text-lg font-bold text-slate-700">{alert.riskScore}</div>
        </div>
      </div>
      <p className="mt-2 text-sm text-slate-600">{alert.trigger}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge tone={escalate ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}>
          {escalate ? 'ESCALATE' : 'DISMISS'}
        </Badge>
        <Badge tone="bg-slate-100 text-slate-600">{Math.round(t.confidence * 100)}% confident</Badge>
        <Badge tone="bg-indigo-100 text-indigo-700">{t.matchedTypology.code}</Badge>
        <Badge tone={flagged ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-500'}>
          verifier: {t.verifier.status}
        </Badge>
      </div>
      {flagged && (
        <p className="mt-2 rounded border-l-4 border-amber-400 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          ⚠ {t.verifier.note}
        </p>
      )}
    </li>
  )
}

export default function App() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [status, setStatus] = useState<AlertStatus | undefined>(undefined)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getAlerts(status)
      .then(setAlerts)
      .finally(() => setLoading(false))
  }, [status])

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">AML Alert-Triage Copilot</h1>
        <p className="text-sm text-slate-500">Analyst queue — Phase 0 shell (mock data)</p>
      </header>

      <div className="mb-4 flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => setStatus(f.value)}
            className={`rounded-full px-3 py-1 text-sm ${
              status === f.value ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-slate-400">Loading…</p>
      ) : (
        <ul className="space-y-3">
          {alerts.map((a) => (
            <AlertCard key={a.alertId} alert={a} />
          ))}
        </ul>
      )}
    </div>
  )
}
