import type { OperationalImpact } from '../types'

const pct = (value: number) => `${Math.round(value * 100)}%`

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded border border-line bg-paper px-3 py-2">
      <div className="text-[10px] font-semibold uppercase text-ink-faint">{label}</div>
      <div className="mt-1 font-mono text-[16px] font-semibold tabular-nums text-ink">{value}</div>
      <div className="mt-0.5 text-[11px] leading-tight text-ink-faint">{sub}</div>
    </div>
  )
}

export function OperationalImpactCard({ impact }: { impact: OperationalImpact | null }) {
  if (!impact) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Operational impact</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Operational impact unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Operational impact</h3>
        <span className="rounded border border-verified bg-verified-soft px-2 py-1 text-[11px] font-medium text-verified">
          shift workload
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{impact.demoNarrative}</p>

      <div className="mt-4 grid gap-2 md:grid-cols-4">
        <Metric label="Inbox removed" value={`${impact.autoClearedAlerts}/${impact.processedAlerts}`} sub={pct(impact.queueReductionRate)} />
        <Metric label="Human queue" value={`${impact.humanReviewAlerts}`} sub={`${impact.reviewFocusMultiplier}x focus`} />
        <Metric label="Hours returned" value={`${impact.analystHoursReturned}h`} sub={`${impact.minutesReturned} minutes`} />
        <Metric label="QA sample" value={`${impact.qaSampleAlerts}`} sub="cleared-lane check" />
      </div>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
        <div>
          <div className="text-[11px] font-semibold uppercase text-ink-faint">Controls kept</div>
          <ul className="mt-2 space-y-1.5">
            {impact.controlChecks.map((item) => (
              <li key={item} className="flex gap-2 text-[12px] leading-relaxed text-ink-soft">
                <span aria-hidden className="shrink-0 font-mono text-verified">+</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase text-ink-faint">Assumptions</div>
          <ul className="mt-2 space-y-1.5">
            {impact.assumptions.map((item) => (
              <li key={item} className="flex gap-2 text-[12px] leading-relaxed text-ink-soft">
                <span aria-hidden className="shrink-0 font-mono text-flag">!</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-faint">{impact.caveat}</p>
    </section>
  )
}
