import type { Metrics } from '../types'

interface MetricsDashboardProps {
  metrics: Metrics | null
}

export function MetricsDashboard({ metrics }: MetricsDashboardProps) {
  return (
    <div className="h-full overflow-y-auto bg-paper p-8">
      <header className="mb-8">
        <h2 className="text-xl font-semibold tracking-tight text-ink">System performance</h2>
        <p className="mt-1 text-[13px] text-ink-soft">
          Workload impact, the human-in-the-loop safety net, and an honest held-out evaluation.
        </p>
      </header>

      {metrics ? (
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Headline: workload removed + time saved (NOT raw accuracy or recall) */}
          <div className="grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-line bg-line">
            <Figure
              label="Benign alerts auto-cleared"
              value={`${(metrics.falsePositiveReduction * 100).toFixed(0)}%`}
              note="Of the alerts the copilot recommends dismissing, the share genuinely benign — the analyst workload removed."
            />
            <Figure
              label="Review time per alert"
              value={`${Math.round(
                ((metrics.avgReviewTimeBaselineMin - metrics.avgReviewTimeWithCopilotMin) /
                  metrics.avgReviewTimeBaselineMin) *
                  100,
              )}% cut`}
              note={`${metrics.avgReviewTimeBaselineMin} → ${metrics.avgReviewTimeWithCopilotMin} min (modeled), redirecting time to deeper investigations.`}
            />
            <Figure
              label="Alerts evaluated"
              value={`${metrics.totalAlerts}`}
              note="Held-out records from the Jensen et al. (2023) Spar Nord dataset, frozen before tuning."
            />
          </div>

          {/* Safety net — the human-in-the-loop guarantee */}
          <div className="rounded-lg border border-line bg-surface p-5">
            <h3 className="text-[14px] font-semibold text-ink">Human-in-the-loop safety net</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
              The copilot never makes the <em>consequential</em> call. Escalations, verifier-flagged alerts,
              and low-confidence dismisses all route to the analyst; the Queue Agent autonomously clears only
              the high-confidence, verifier-agreed benign noise — dismiss-only, sampled, and audited — and
              never auto-escalates or auto-files. It triages <em>alerts</em>, not the raw transaction firehose
              the bank's monitoring system already reduces, so its value is workload removed on the safe side,
              with the human gate kept exactly where the regulator demands it.
            </p>
          </div>

          {/* Autonomous queue agent (ADR-0010) — the two numbers paired with the honest caveat */}
          {metrics.autoClearedShare != null && metrics.autoClearPrecision != null && (
            <div className="rounded-lg border border-line bg-surface p-6">
              <h3 className="text-[14px] font-semibold text-ink">Autonomous queue agent — what it clears, and what it can't</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
                The Queue Agent works the queue unattended and auto-dismisses <strong>only</strong>{' '}
                high-confidence, verifier-agreed benign alerts — dismiss-only, never auto-escalating or
                auto-filing. Measured on the held-out slice:
              </p>

              <div className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line">
                <MiniStat
                  label="Queue auto-cleared"
                  value={`${(metrics.autoClearedShare * 100).toFixed(0)}%`}
                  sub="handled unattended"
                />
                <MiniStat
                  label="Auto-clear precision"
                  value={`${(metrics.autoClearPrecision * 100).toFixed(0)}%`}
                  sub="of auto-cleared, truly benign"
                />
              </div>

              <p className="mt-4 text-[13px] leading-relaxed text-ink-soft">
                Stated honestly: the remaining {((1 - metrics.autoClearPrecision) * 100).toFixed(0)}% of
                auto-cleared alerts were in fact reportable (held-out catch-rate{' '}
                {(metrics.recall * 100).toFixed(0)}%) — the structural recall ceiling of any single-account
                view. That residual is contained by <strong>human sampling of the auto-cleared lane</strong>{' '}
                and is the exact gap the <strong>Mule-Network roadmap</strong> closes with cross-account link
                analysis. The human is never removed; the agent removes the benign noise.
              </p>
            </div>
          )}

          {/* Held-out eval — presented honestly as a conservative floor */}
          <div className="rounded-lg border border-line bg-surface p-6">
            <h3 className="text-[14px] font-semibold text-ink">Held-out evaluation — a conservative floor</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
              Measured on real held-out alerts using only the public dataset's <strong>aggregated,
              amount-less features</strong> — no transaction amounts, running balances, or counterparties. That
              strips out the very signals the copilot reasons over in production (shown live in the demo), so
              these numbers are a floor, not the ceiling. We also don't lead with raw accuracy: on this
              imbalanced base rate, a do-nothing model that dismisses everything scores{' '}
              {(metrics.baselineAccuracy * 100).toFixed(0)}% while catching zero criminals.
            </p>

            <div className="mt-5 grid grid-cols-3 gap-px overflow-hidden rounded-md border border-line bg-line">
              <MiniStat label="Always-dismiss baseline" value={`${(metrics.baselineAccuracy * 100).toFixed(0)}%`} sub="accuracy · 0% caught" />
              <MiniStat label="Copilot accuracy" value={`${(metrics.accuracyVsLabels * 100).toFixed(0)}%`} sub="vs labels" />
              <MiniStat label="False-positive reduction" value={`${(metrics.falsePositiveReduction * 100).toFixed(0)}%`} sub="benign alerts cleared" />
            </div>
          </div>

          {/* Review time (modeled) */}
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
              About {(metrics.avgReviewTimeBaselineMin - metrics.avgReviewTimeWithCopilotMin).toFixed(1)} minutes
              saved per alert, redirecting analyst time to deeper investigations.
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

function MiniStat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="bg-surface p-4">
      <div className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="mt-1.5 font-mono text-2xl font-semibold tabular-nums text-ink">{value}</div>
      <div className="mt-1 text-[11px] text-ink-faint">{sub}</div>
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
