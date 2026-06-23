import type { Alert, AlertStatus } from '../types'

interface AlertQueueProps {
  alerts: Alert[]
  loading: boolean
  filterStatus: AlertStatus | 'all'
  onFilterChange: (status: AlertStatus | 'all') => void
  selectedAlertId: string | null
  onSelect: (alertId: string) => void
  /** Alert currently mid-"Analyzing…" during a demo replay (null when idle). */
  analyzingId?: string | null
  /** When provided, renders a ▶ Replay button that triggers the demo replay. */
  onReplay?: () => void
}

const FILTERS = ['all', 'pending', 'approved', 'overridden'] as const

const statusColor: Record<AlertStatus, string> = {
  pending: 'text-flag',
  approved: 'text-verified',
  overridden: 'text-ink-soft',
}

export function AlertQueue({
  alerts,
  loading,
  filterStatus,
  onFilterChange,
  selectedAlertId,
  onSelect,
  analyzingId,
  onReplay,
}: AlertQueueProps) {
  return (
    <>
      {/* Filters */}
      <div className="flex items-center gap-4 border-b border-line px-5 py-2.5">
        {FILTERS.map((status) => (
          <button
            key={status}
            onClick={() => onFilterChange(status)}
            className={`text-[12px] capitalize transition-colors ${
              filterStatus === status
                ? 'font-semibold text-ink'
                : 'text-ink-faint hover:text-ink-soft'
            }`}
          >
            {status}
          </button>
        ))}
        {onReplay && (
          <button
            onClick={onReplay}
            title="Replay the triage queue (demo)"
            className="ml-auto rounded border border-line px-2 py-0.5 text-[11px] font-semibold text-flag transition-colors hover:bg-paper"
          >
            ▶ Replay
          </button>
        )}
      </div>

      {/* List */}
      <div className="grow overflow-y-auto">
        {loading ? (
          <div className="px-5 py-10 text-center text-[13px] text-ink-faint">Loading queue…</div>
        ) : alerts.length === 0 ? (
          <div className="px-5 py-10 text-center text-[13px] text-ink-faint">No alerts in this view</div>
        ) : (
          <ul>
            {alerts.map((a) => {
              const isSelected = selectedAlertId === a.alertId
              const escalate = a.triage.recommendation === 'escalate'
              const flagged = a.triage.verifier.status === 'flagged'

              return (
                <li key={a.alertId}>
                  <button
                    onClick={() => onSelect(a.alertId)}
                    className={`block w-full border-b border-line border-l-2 px-5 py-3 text-left transition-colors ${
                      isSelected
                        ? 'border-l-ink bg-paper'
                        : 'border-l-transparent hover:bg-paper'
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-mono text-[12px] text-ink-soft">{a.alertId}</span>
                      <span className={`label ${statusColor[a.status]}`}>{a.status}</span>
                    </div>

                    <div className="mt-1 truncate text-[14px] font-medium text-ink">{a.account.holderName}</div>
                    <p className="mt-0.5 truncate text-[12px] text-ink-faint">{a.trigger}</p>

                    {analyzingId === a.alertId ? (
                      <div className="mt-2 flex items-center gap-2 text-[12px] text-ink-faint">
                        <span className="h-3 w-3 animate-spin rounded-full border-2 border-line-strong border-t-ink" />
                        <span className="animate-pulse">Analyzing…</span>
                      </div>
                    ) : (
                      <div className="mt-2 flex items-center gap-3 text-[12px]">
                        <span className={`font-semibold ${escalate ? 'text-escalate' : 'text-verified'}`}>
                          {escalate ? 'Escalate' : 'Dismiss'}
                        </span>
                        <span className="font-mono text-ink-faint tabular-nums">
                          {Math.round(a.triage.confidence * 100)}%
                        </span>
                        {flagged && <span className="ml-auto font-medium text-flag">Flagged</span>}
                      </div>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </>
  )
}
