import type { Metrics } from '../types'

interface MetricsSnapshotProps {
  metrics: Metrics | null
}

// Sidebar "triage desk health" — reads the SAME real /metrics data as MetricsDashboard
// (no hardcoded figures). Mirrors the dashboard's honest headline trio so nothing on
// screen contradicts the measured held-out numbers.
export function MetricsSnapshot({ metrics }: MetricsSnapshotProps) {
  return (
    <div className="px-5 py-5">
      <div className="label mb-3">Triage desk health</div>
      {metrics ? (
        <dl className="space-y-2.5">
          <Row
            label="Catch rate (recall)"
            value={`${(metrics.recall * 100).toFixed(0)}%`}
            tone="text-verified"
          />
          <Row
            label="Review time saved"
            value={`-${Math.round(
              ((metrics.avgReviewTimeBaselineMin - metrics.avgReviewTimeWithCopilotMin) /
                metrics.avgReviewTimeBaselineMin) *
                100,
            )}%`}
            tone="text-ink"
          />
          <Row label="Alerts evaluated" value={`${metrics.totalAlerts}`} tone="text-ink" />
        </dl>
      ) : (
        <p className="text-[12px] text-ink-faint">Loading metrics…</p>
      )}
    </div>
  )
}

function Row({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-line pb-2 last:border-0">
      <dt className="text-[13px] text-ink-soft">{label}</dt>
      <dd className={`font-mono text-[13px] font-medium tabular-nums ${tone}`}>{value}</dd>
    </div>
  )
}
