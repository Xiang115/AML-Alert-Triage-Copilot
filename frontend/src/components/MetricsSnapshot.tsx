// NOTE: these figures are hardcoded (pre-existing), unlike the live MetricsDashboard
// which reads from /metrics. Left as-is to preserve behaviour during decomposition.
const ROWS = [
  { label: 'Accuracy', value: '94.2%', tone: 'text-ink' },
  { label: 'FP reduction', value: '68.0%', tone: 'text-ink' },
  { label: 'Review time saved', value: '−77%', tone: 'text-verified' },
]

export function MetricsSnapshot() {
  return (
    <div className="px-5 py-5">
      <div className="label mb-3">Triage desk health</div>
      <dl className="space-y-2.5">
        {ROWS.map((row) => (
          <div key={row.label} className="flex items-baseline justify-between border-b border-line pb-2 last:border-0">
            <dt className="text-[13px] text-ink-soft">{row.label}</dt>
            <dd className={`font-mono text-[13px] font-medium tabular-nums ${row.tone}`}>{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
