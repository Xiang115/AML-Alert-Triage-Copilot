import type { Metrics, TypologyRecall } from '../types'
import { EvaluationSet } from './EvaluationSet'

// Card code -> human label for the per-typology recall bars (ADR-0012). COVERAGE_GAP is the
// bucket of true Reports whose pattern maps to no card — the quantified KB-coverage limit.
const TYPOLOGY_NAMES: Record<string, string> = {
  'PT-01': 'Pass-through / rapid movement',
  'FI-01': 'Fan-in / consolidation',
  'ST-01': 'Structuring / smurfing',
  'DA-01': 'Dormant-then-active',
  'KYC-01': 'KYC profile mismatch',
  COVERAGE_GAP: 'Outside the 5-card KB (coverage gap)',
}

interface MetricsDashboardProps {
  metrics: Metrics | null
}

export function MetricsDashboard({ metrics }: MetricsDashboardProps) {
  return (
    <div className="h-full overflow-y-auto bg-paper p-8">
      <header className="mb-8">
        <h2 className="text-xl font-semibold tracking-tight text-ink">System performance</h2>
        <p className="mt-1 text-[13px] text-ink-soft">
          Measured on real, public AML data (SAML-D) — workload impact, the human-in-the-loop safety
          net, and an honest held-out evaluation that leads with catch-rate, not accuracy.
        </p>
      </header>

      {metrics ? (
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Headline: lead with recall (the mix-independent truth, ADR-0012) + beats-baseline + time */}
          <div className="grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-line bg-line">
            <Figure
              label="Catch rate (recall)"
              value={`${(metrics.recall * 100).toFixed(0)}%`}
              note="Of true reports in the held-out slice, the share the copilot caught. The mix-independent headline — lead with this, not accuracy (ADR-0012)."
            />
            <Figure
              label="Beats always-dismiss baseline"
              value={`+${((metrics.accuracyVsLabels - metrics.baselineAccuracy) * 100).toFixed(0)} pts`}
              note={`${(metrics.accuracyVsLabels * 100).toFixed(0)}% accuracy vs ${(metrics.baselineAccuracy * 100).toFixed(0)}% for always dismissing this held-out slice — the baseline catches zero reportable cases.`}
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
          </div>

          {/* Per-typology recall (ADR-0012) — the payoff: fan-in/structuring, unmeasurable on
              SynthAML, are now the strongest detectors on amount-bearing data. */}
          {metrics.perTypologyRecall && (
            <div className="rounded-lg border border-line bg-surface p-6">
              <h3 className="text-[14px] font-semibold text-ink">Per-typology catch rate</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
                Held-out recall within each true money-laundering typology. Fan-in (FI-01) and
                structuring (ST-01) were <em>structurally unmeasurable</em> on SynthAML's amount-less
                features; on SAML-D they fire — and lead.
              </p>

              <div className="mt-5 space-y-3.5">
                {sortedTypologies(metrics.perTypologyRecall).map(([code, r]) => (
                  <TypologyBar key={code} code={code} recall={r} />
                ))}
              </div>

              <p className="mt-5 border-t border-line pt-4 text-[12px] leading-relaxed text-ink-faint">
                {metrics.measuredTypologies && (
                  <>
                    <strong className="text-ink-soft">
                      {metrics.measuredTypologies.length} of{' '}
                      {metrics.measuredTypologies.length + (metrics.roadmapTypologies?.length ?? 0)} cards
                      measured
                    </strong>{' '}
                    across SAML-D + SynthAML (DA-01 on SynthAML).{' '}
                  </>
                )}
                KYC-01 is the honest residual — no public dataset carries the declared customer profile
                it needs.
              </p>
            </div>
          )}

          {/* Held-out eval — honest framing for SAML-D (report-enriched mix; lead with recall) */}
          <div className="rounded-lg border border-line bg-surface p-6">
            <h3 className="text-[14px] font-semibold text-ink">Held-out evaluation — stated honestly</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
              Measured on {metrics.totalAlerts} real held-out SAML-D alerts (Oztas et al., 2023), frozen
              before tuning, with no label leakage. The slice is <strong>report-enriched
              (~60% positive)</strong> for measurement power, so accuracy and precision reflect that mix,
              not the real ~0.1% base rate — <strong>recall is the mix-independent truth</strong>. On the
              held-out slice, the {(metrics.baselineAccuracy * 100).toFixed(0)}% baseline is simply the
              benign share: an always-dismiss model marks every alert benign, gets those benign cases right,
              and catches zero reportable cases.
            </p>

            <div className="mt-5 grid grid-cols-3 gap-px overflow-hidden rounded-md border border-line bg-line">
              <MiniStat label="Recall (catch rate)" value={`${(metrics.recall * 100).toFixed(0)}%`} sub="of true reports caught" />
              <MiniStat label="Precision" value={`${(metrics.precision * 100).toFixed(0)}%`} sub="of escalations, truly reportable" />
              <MiniStat label="Specificity" value={`${(metrics.specificity * 100).toFixed(0)}%`} sub="of benign, correctly dismissed" />
            </div>

            <ConfusionMatrix cm={metrics.confusionMatrix} />

            {metrics.coverageNote && (
              <p className="mt-5 border-t border-line pt-4 text-[12px] leading-relaxed text-ink-faint">
                {metrics.coverageNote}
              </p>
            )}
          </div>

          {/* The held-out set itself, made visible (token-free) — the 250 alerts behind the number */}
          <EvaluationSet />

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

              <div
                className={`mt-5 grid gap-px overflow-hidden rounded-md border border-line bg-line ${
                  metrics.autoClearLeakageRate != null ? 'grid-cols-3' : 'grid-cols-2'
                }`}
              >
                <MiniStat
                  label="Queue auto-cleared"
                  value={`${(metrics.autoClearedShare * 100).toFixed(0)}%`}
                  sub="handled unattended"
                />
                {metrics.autoClearLeakageRate != null && (
                  <MiniStat
                    label="Auto-clear leakage"
                    value={`${(metrics.autoClearLeakageRate * 100).toFixed(0)}%`}
                    sub={`of true reports (${metrics.autoClearedReports}/${metrics.totalReports}) auto-cleared`}
                  />
                )}
                <MiniStat
                  label="Auto-clear precision"
                  value={`${(metrics.autoClearPrecision * 100).toFixed(0)}%`}
                  sub="of auto-cleared, truly benign"
                />
              </div>

              <p className="mt-4 text-[13px] leading-relaxed text-ink-soft">
                Stated honestly:{' '}
                {metrics.autoClearLeakageRate != null ? (
                  <>
                    of the true reports in this slice,{' '}
                    <strong>
                      {(metrics.autoClearLeakageRate * 100).toFixed(0)}% ({metrics.autoClearedReports}/
                      {metrics.totalReports})
                    </strong>{' '}
                    would be auto-cleared unsupervised — the <strong>mix-independent</strong> leakage (like
                    recall, it doesn&rsquo;t move with the base rate), the structural recall ceiling of any
                    single-account view.
                  </>
                ) : (
                  <>
                    the remaining {((1 - metrics.autoClearPrecision) * 100).toFixed(0)}% of auto-cleared
                    alerts were in fact reportable — the structural recall ceiling of any single-account view.
                  </>
                )}{' '}
                That is exactly why auto-clear is <strong>never unsupervised</strong>: a risk-weighted{' '}
                <strong>QA sample of the auto-cleared lane</strong> routes the least-sure clears back to a
                human, and the <strong>Mule-Network roadmap</strong> closes the rest with cross-account link
                analysis. The human is never removed; the agent removes the benign noise.
              </p>
            </div>
          )}

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

// KB cards first (by recall desc), the COVERAGE_GAP bucket last — so the chart reads
// "the cards we model >> patterns outside the library".
function sortedTypologies(per: Record<string, TypologyRecall>): [string, TypologyRecall][] {
  return Object.entries(per).sort(([a, ra], [b, rb]) => {
    if (a === 'COVERAGE_GAP') return 1
    if (b === 'COVERAGE_GAP') return -1
    return (rb.recall ?? 0) - (ra.recall ?? 0)
  })
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

function TypologyBar({ code, recall }: { code: string; recall: TypologyRecall }) {
  const pct = recall.recall === null ? 0 : Math.round(recall.recall * 100)
  const isGap = code === 'COVERAGE_GAP'
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-[13px] text-ink-soft">
          {!isGap && <span className="font-mono text-[12px] text-ink-faint">{code} · </span>}
          {TYPOLOGY_NAMES[code] ?? code}
        </span>
        <span className="shrink-0 font-mono text-[13px] font-medium tabular-nums text-ink">
          {pct}% <span className="text-[11px] text-ink-faint">({recall.caught}/{recall.total})</span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-paper">
        <div className={`h-full rounded-full ${isGap ? 'bg-line-strong' : 'bg-ink'}`} style={{ width: `${pct}%` }}></div>
      </div>
    </div>
  )
}

// 2x2 confusion matrix with plain-language axes so a non-ML reader can parse it: rows = what the
// model said, columns = ground truth. TP/TN are the wins (tinted), FP/FN the errors.
function ConfusionMatrix({ cm }: { cm: { tp: number; fp: number; fn: number; tn: number } }) {
  return (
    <div className="mt-5">
      <div className="label mb-2">Confusion matrix — model call vs. ground truth</div>
      <div className="overflow-hidden rounded-md border border-line">
        <div className="grid grid-cols-[auto_1fr_1fr] text-[12px]">
          <div className="bg-surface p-2"></div>
          <div className="bg-surface p-2 text-center font-medium text-ink-soft">Actually a report</div>
          <div className="bg-surface p-2 text-center font-medium text-ink-soft">Actually benign</div>

          <div className="flex items-center bg-surface p-2 font-medium text-ink-soft">Model: escalate</div>
          <Cell value={cm.tp} label="caught" tone="bg-verified-soft text-verified" />
          <Cell value={cm.fp} label="false alarm" tone="text-ink-soft" />

          <div className="flex items-center bg-surface p-2 font-medium text-ink-soft">Model: dismiss</div>
          <Cell value={cm.fn} label="missed report" tone="text-escalate" />
          <Cell value={cm.tn} label="correct clear" tone="bg-verified-soft text-verified" />
        </div>
      </div>
    </div>
  )
}

function Cell({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div className={`border-l border-t border-line p-3 text-center ${tone}`}>
      <div className="font-mono text-xl font-semibold tabular-nums">{value}</div>
      <div className="mt-0.5 text-[11px] opacity-80">{label}</div>
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
