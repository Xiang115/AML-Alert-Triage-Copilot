import type { Alert, AlertStatus } from '../types'

interface AlertQueueProps {
  alerts: Alert[]
  loading: boolean
  filterStatus: AlertStatus | 'all'
  onFilterChange: (status: AlertStatus | 'all') => void
  selectedAlertId: string | null
  onSelect: (alertId: string) => void
}

export function AlertQueue({
  alerts,
  loading,
  filterStatus,
  onFilterChange,
  selectedAlertId,
  onSelect,
}: AlertQueueProps) {
  return (
    <>
      {/* Filter Pills */}
      <div className="flex gap-1 overflow-x-auto p-2 bg-slate-950/20 border-b border-slate-900/60">
        {(['all', 'pending', 'approved', 'overridden'] as const).map((status) => (
          <button
            key={status}
            onClick={() => onFilterChange(status)}
            className={`rounded px-2 py-0.5 text-3xs font-semibold capitalize tracking-wide transition-all ${
              filterStatus === status
                ? 'bg-teal-950/40 text-teal-400 border border-teal-800/40'
                : 'bg-slate-900/30 text-slate-500 hover:bg-slate-900/60 hover:text-slate-300'
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="flex-grow overflow-y-auto p-2 space-y-1.5">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-10 text-slate-500">
            <div className="h-4 w-4 animate-spin rounded-full border border-teal-500 border-t-transparent mb-2"></div>
            <span className="text-3xs">Loading queue...</span>
          </div>
        ) : alerts.length === 0 ? (
          <div className="py-10 text-center text-3xs text-slate-600">No active alerts</div>
        ) : (
          alerts.map((a) => {
            const isSelected = selectedAlertId === a.alertId
            const escalate = a.triage.recommendation === 'escalate'
            const verifierFlagged = a.triage.verifier.status === 'flagged'

            return (
              <div
                key={a.alertId}
                onClick={() => onSelect(a.alertId)}
                className={`group relative cursor-pointer rounded-lg border p-3 transition-all duration-150 ${
                  isSelected
                    ? 'border-teal-500/60 bg-teal-950/5 shadow shadow-teal-950/10'
                    : 'border-slate-900 bg-slate-950/20 hover:border-slate-800/80 hover:bg-slate-950/40'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-3xs font-semibold text-slate-400">{a.alertId}</span>
                      <span className="h-0.5 w-0.5 rounded-full bg-slate-700"></span>
                      <span className={`text-3xs font-bold tracking-wider uppercase ${
                        a.status === 'pending'
                          ? 'text-amber-500/90'
                          : a.status === 'approved'
                          ? 'text-emerald-500/90'
                          : 'text-rose-500/90'
                      }`}>
                        {a.status}
                      </span>
                    </div>
                    <div className="mt-1 font-semibold text-xs text-slate-200 group-hover:text-white transition-colors">
                      {a.account.holderName}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="block text-3xs font-medium text-slate-500 uppercase tracking-wide">Risk</span>
                    <span className="text-xs font-black text-slate-300">{a.riskScore}</span>
                  </div>
                </div>

                <p className="mt-1.5 text-3xs text-slate-400 truncate leading-relaxed">{a.trigger}</p>

                <div className="mt-2.5 flex items-center justify-between border-t border-slate-900/50 pt-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-3xs font-bold tracking-wide uppercase ${
                      escalate ? 'text-rose-400/95' : 'text-emerald-400/95'
                    }`}>
                      {escalate ? 'ESCALATE' : 'DISMISS'}
                    </span>
                    <span className="font-mono text-3xs text-slate-500">
                      {Math.round(a.triage.confidence * 100)}% conf
                    </span>
                  </div>
                  {verifierFlagged && (
                    <span className="flex items-center gap-1 text-3xs font-semibold text-amber-500/90">
                      <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      Flagged
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </>
  )
}
