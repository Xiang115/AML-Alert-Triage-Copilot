import type { GovernanceThresholds, Metrics } from '../types'
import { Badge } from './ui/Badge'

interface AutoClearDefenseProps {
  metrics: Metrics | null
  thresholds: GovernanceThresholds | null
  qaSampleCount: number
}

const pct = (n: number | null | undefined) => (n == null ? '--' : `${Math.round(n * 100)}%`)

function autoClearLeakage(metrics: Metrics): { rate: number; leaked: number; totalReports: number } | null {
  if (metrics.autoClearLeakageRate != null && metrics.autoClearedReports != null && metrics.totalReports != null) {
    return {
      rate: metrics.autoClearLeakageRate,
      leaked: metrics.autoClearedReports,
      totalReports: metrics.totalReports,
    }
  }
  if (metrics.autoClearedShare == null || metrics.autoClearPrecision == null) return null
  const cm = metrics.confusionMatrix
  const n = cm.tp + cm.fp + cm.fn + cm.tn
  const autoCleared = Math.round(metrics.autoClearedShare * n)
  const benign = Math.round(metrics.autoClearPrecision * autoCleared)
  const leaked = Math.max(0, autoCleared - benign)
  const totalReports = cm.tp + cm.fn
  return totalReports ? { rate: leaked / totalReports, leaked, totalReports } : null
}

export function AutoClearDefense({ metrics, thresholds, qaSampleCount }: AutoClearDefenseProps) {
  if (!metrics || metrics.autoClearedShare == null || metrics.autoClearPrecision == null) return null

  const leak = autoClearLeakage(metrics)
  const leakage = leak
    ? `${pct(leak.rate)} (${leak.leaked}/${leak.totalReports})`
    : 'not measured'
  const autoClearLine = thresholds ? pct(thresholds.autoClear) : 'configured threshold'
  const qaRate = thresholds ? pct(thresholds.qaSample) : 'risk-weighted'

  return (
    <section className="mt-2 rounded-md border border-line bg-surface p-2.5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Auto-clear defense</h3>
        <Badge tone="bg-paper text-ink-soft">dismiss-only</Badge>
      </div>

      <p className="mt-1 max-h-8 overflow-hidden text-[11px] leading-4 text-ink-soft">
        Policy: <strong className="text-ink">dismiss</strong> + verifier agreed + confidence at/above{' '}
        <strong className="text-ink">{autoClearLine}</strong>. It never auto-escalates and never files an
        STR.
      </p>

      <div className="mt-2 grid grid-cols-3 gap-px overflow-hidden rounded border border-line bg-line">
        <Mini label="Cleared" value={pct(metrics.autoClearedShare)} sub="of queue" />
        <Mini label="Leakage" value={leakage} sub="P(cleared | true report)" danger={!!leak} />
        <Mini label="QA sample" value={`${qaSampleCount}`} sub={`${qaRate} spot-check`} danger={qaSampleCount > 0} />
      </div>

      <p className="mt-1 max-h-8 overflow-hidden text-[10px] leading-4 text-ink-faint">
        The point is not a prettier number: the queue exposes the failure mode, samples the riskiest clears,
        and records every clear in audit.
      </p>
    </section>
  )
}

function Mini({ label, value, sub, danger = false }: { label: string; value: string; sub: string; danger?: boolean }) {
  return (
    <div className="bg-surface px-2 py-1.5">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{label}</div>
      <div className={`mt-0.5 font-mono text-[13px] font-semibold tabular-nums ${danger ? 'text-flag' : 'text-ink'}`}>
        {value}
      </div>
      <div className="mt-0.5 text-[10px] leading-tight text-ink-faint">{sub}</div>
    </div>
  )
}
