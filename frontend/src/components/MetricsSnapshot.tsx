// NOTE: these figures are hardcoded (pre-existing), unlike the live MetricsDashboard
// which reads from /metrics. Left as-is to preserve behaviour during decomposition.
export function MetricsSnapshot() {
  return (
    <div className="p-4 space-y-4 text-2xs text-slate-400">
      <div className="rounded-lg bg-slate-950/40 p-3.5 border border-slate-900">
        <div className="text-slate-500 font-bold uppercase tracking-wider text-3xs">Triage Desk Health</div>
        <div className="mt-2.5 space-y-2 font-medium">
          <div className="flex justify-between border-b border-slate-900/50 pb-1.5">
            <span>Accuracy:</span>
            <strong className="text-slate-200">94.2%</strong>
          </div>
          <div className="flex justify-between border-b border-slate-900/50 pb-1.5">
            <span>FP Reduction:</span>
            <strong className="text-slate-200">68.0%</strong>
          </div>
          <div className="flex justify-between">
            <span>Review Savings:</span>
            <strong className="text-emerald-400">-77% Time</strong>
          </div>
        </div>
      </div>
    </div>
  )
}
