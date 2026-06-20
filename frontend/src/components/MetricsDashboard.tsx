import type { Metrics } from '../types'

interface MetricsDashboardProps {
  metrics: Metrics | null
}

export function MetricsDashboard({ metrics }: MetricsDashboardProps) {
  return (
    <div className="h-full overflow-y-auto bg-paper p-8">
      <header className="mb-8">
        <h2 className="text-xl font-semibold tracking-tight text-ink">System performance</h2>
        <p className="mt-1 text-[13px] text-ink-soft">Measured on the held-out SynthAML evaluation slice.</p>
      </header>

      {metrics ? (
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Headline figures */}
          <div className="grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-line bg-line">
            <Figure
              label="Triage accuracy"
              value={`${(metrics.accuracyVsLabels * 100).toFixed(1)}%`}
              note="Recommendation alignment with validated bank outcomes."
            />
            <Figure
              label="False-positive reduction"
              value={`${(metrics.falsePositiveReduction * 100).toFixed(0)}%`}
              note="Benign alerts resolved without manual triage."
            />
            <Figure
              label="Alerts evaluated"
              value={`${metrics.totalAlerts}`}
              note="Held-out records from the Jensen et al. (2023) Spar Nord dataset."
            />
          </div>

          {/* Review time */}
          <div className="rounded-lg border border-line bg-surface p-6">
            <h3 className="text-[14px] font-semibold text-ink">Review time per alert</h3>
            <p className="mt-1 text-[13px] text-ink-soft">Baseline manual triage vs Copilot-assisted (modeled).</p>

            <div className="mt-5 space-y-4">
              <Bar
                label="Manual baseline"
                value={`${metrics.avgReviewTimeBaselineMin} min`}
                width="100%"
                tone="bg-line-strong"
                emphasis="text-ink-soft"
              />
              <Bar
                label="Copilot-assisted"
                value={`${metrics.avgReviewTimeWithCopilotMin} min`}
                width={`${(metrics.avgReviewTimeWithCopilotMin / metrics.avgReviewTimeBaselineMin) * 100}%`}
                tone="bg-ink"
                emphasis="text-ink"
              />
            </div>

            <p className="mt-5 border-t border-line pt-4 text-[13px] text-ink-soft">
              About 9.5 minutes saved per alert, redirecting analyst time to deeper investigations.
            </p>
          </div>
        </div>
      ) : (
        <div className="py-20 text-center text-[13px] text-ink-faint">Couldn't load system metrics.</div>
      )}
    </div>
  )
}

function Figure({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="bg-surface p-5">
      <div className="label">{label}</div>
      <div className="mt-2 font-mono text-3xl font-semibold tabular-nums text-ink">{value}</div>
      <p className="mt-2 text-[12px] leading-relaxed text-ink-faint">{note}</p>
    </div>
  )
}

function Bar({
  label,
  value,
  width,
  tone,
  emphasis,
}: {
  label: string
  value: string
  width: string
  tone: string
  emphasis: string
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-[13px] text-ink-soft">{label}</span>
        <span className={`font-mono text-[13px] font-medium tabular-nums ${emphasis}`}>{value}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-paper">
        <div className={`h-full rounded-full ${tone}`} style={{ width }}></div>
      </div>
    </div>
  )
}
