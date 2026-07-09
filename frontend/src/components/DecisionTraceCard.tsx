import type { Alert, AuditEntry, DecisionTrace, DecisionTraceStep, GovernanceThresholds } from '../types'
import { Badge } from './ui/Badge'
import { TracedClaimList } from './TracedClaimList'

function pct(n: number) {
  return `${Math.round(n * 100)}%`
}

function toneForResult(result: string): string {
  if (result.includes('blocked') || result === 'flagged' || result === 'present' || result === 'locked') {
    return 'bg-flag-soft text-flag'
  }
  if (result === 'fired' || result === 'agreed' || result === 'canFile' || result === 'autoCleared') {
    return 'bg-verified-soft text-verified'
  }
  return 'bg-paper text-ink-soft'
}

function stepLabel(step: DecisionTraceStep): string {
  if (step.step === 'indicatorEvaluation') return 'indicator'
  if (step.step === 'confidenceComputation') return 'confidence'
  if (step.step === 'routePolicy') return 'routing'
  if (step.step === 'strFilingGate') return 'STR gate'
  return step.step.replace('Gate', ' gate')
}

// Routing defense (folded in from the former DefenseCase): the human-readable "why this lane",
// derived from the same triage output + thresholds the deterministic gates below act on.
function routingDefense(alert: Alert, thresholds: GovernanceThresholds | null): string {
  const t = alert.triage
  const autoClearLine = thresholds?.autoClear ?? 0.85
  const reviewLine = thresholds?.review ?? 0.6

  if (t.recommendation === 'escalate') {
    return 'Needs review: escalation is a consequential call and can never be auto-cleared or auto-filed.'
  }
  if (t.debate) {
    return 'Needs review: the agents entered adversarial debate, so the firewall prevents auto-clear.'
  }
  if (t.verifier.status === 'flagged') {
    return 'Needs review: the verifier challenged the dismiss call, so the clear is blocked.'
  }
  if (t.screening?.blocked) {
    return 'Needs review: screening found a counterparty hit or potential hit.'
  }
  if (alert.routing === 'autoCleared' && t.suppression?.status === 'suppressed') {
    return `Auto-cleared by learned suppression: dismiss + verifier agreed + confidence above ${pct(reviewLine)} review line + benign-consistent envelope.`
  }
  if (alert.routing === 'autoCleared' || t.confidence >= autoClearLine) {
    return `Auto-clear eligible: dismiss + verifier agreed + confidence at or above ${pct(autoClearLine)}.`
  }
  return `Needs review: dismiss + verifier agreed, but confidence is below the ${pct(autoClearLine)} auto-clear line.`
}

function goamlDefense(alert: Alert): string {
  if (!alert.triage.strDraft) return 'No STR generated: current disposition is dismiss.'
  if (alert.status === 'pending') return 'STR draft exists, but goAML export is locked until analyst sign-off.'
  return 'goAML export is unlocked after analyst sign-off and remains schema-validated server-side.'
}

function auditSummary(entries: AuditEntry[]): string {
  if (entries.length === 0) return 'No audit event recorded for this alert yet.'
  const counts = entries.reduce<Record<string, number>>((acc, e) => {
    acc[e.event] = (acc[e.event] ?? 0) + 1
    return acc
  }, {})
  return Object.entries(counts)
    .map(([event, count]) => `${event} x${count}`)
    .join(' / ')
}

interface DecisionTraceCardProps {
  // Observable gate trace (formula + deterministic steps); null when the backend didn't supply one.
  trace: DecisionTrace | null
  // The alert itself is the source of truth for the headline call + the defense prose, so the card
  // stays meaningful even when `trace` is null.
  alert: Alert
  thresholds: GovernanceThresholds | null
  auditEntries: AuditEntry[]
}

// The single decision card: the observable deterministic trace (formula + gate table) and the
// human-readable defense (routing rationale, operating point, adversarial check, STR/goAML gate,
// audit replay) in one place. Recommendation/confidence/indicators — which the two former cards
// both repeated — are shown once, sourced from the served triage output.
export function DecisionTraceCard({ trace, alert, thresholds, auditEntries }: DecisionTraceCardProps) {
  const t = alert.triage
  const fired = t.indicatorCoverage.fired.length
  const total = t.indicatorCoverage.indicators.length
  const cited = t.citedTransactionIds.length
  const routing = alert.routing ?? 'needsReview'
  const routingTone = routing === 'autoCleared' ? 'bg-verified-soft text-verified' : 'bg-flag-soft text-flag'
  const verifierTone = t.verifier.status === 'agreed' ? 'bg-verified-soft text-verified' : 'bg-flag-soft text-flag'
  const gateSteps = trace ? trace.steps.filter((step) => step.step !== 'indicatorEvaluation') : []

  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="label">Decision trace</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
            Observable replay of why this alert was routed — from the stored triage output through the deterministic gates.
          </p>
        </div>
        <Badge tone={routingTone}>{routing}</Badge>
      </div>

      {/* Shared headline — shown once (both former cards repeated it). */}
      <dl className="mt-4 grid grid-cols-3 gap-3 text-[12px]">
        <div>
          <dt className="label">Recommendation</dt>
          <dd className="mt-1 font-semibold text-ink">{t.recommendation}</dd>
        </div>
        <div>
          <dt className="label">Confidence</dt>
          <dd className="mt-1 font-mono text-ink">{pct(t.confidence)}</dd>
        </div>
        <div>
          <dt className="label">Indicators</dt>
          <dd className="mt-1 font-mono text-ink">{fired}/{total}</dd>
        </div>
      </dl>

      <dl className="mt-4 space-y-3 text-[13px]">
        <div>
          <dt className="label">Evidence basis</dt>
          <dd className="mt-1 text-ink">
            {t.matchedTypology.code} - {t.matchedTypology.name}
            <span className="text-ink-soft"> / {fired}/{total} indicators fired / {cited} cited txns</span>
          </dd>
        </div>

        {thresholds && (
          <div>
            <dt className="label">Operating point</dt>
            <dd className="mt-1 font-mono text-[12px] text-ink-soft">
              confidence {pct(t.confidence)} / review {pct(thresholds.review)} / auto-clear {pct(thresholds.autoClear)}
              {alert.borderlineDismiss ? ' / borderline dismiss' : ''}
              {alert.qaSampled ? ' / QA sampled' : ''}
            </dd>
          </div>
        )}

        <div>
          <dt className="label">Routing defense</dt>
          <dd className="mt-1 text-ink-soft">{routingDefense(alert, thresholds)}</dd>
        </div>
      </dl>

      {/* Observable trace — the deterministic gates the routing rests on. */}
      {trace ? (
        <>
          <div className="mt-4 rounded-md border border-line bg-paper px-3 py-2">
            <div className="label">Formula</div>
            <p className="mt-1 font-mono text-[11px] leading-relaxed text-ink-soft">{trace.formula}</p>
          </div>

          <div className="mt-4 overflow-hidden rounded-md border border-line">
            <table className="w-full border-collapse text-left">
              <thead className="bg-paper">
                <tr className="border-b border-line">
                  <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Step</th>
                  <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Result</th>
                  <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {gateSteps.map((step) => (
                  <tr key={`${step.step}-${step.label}`} className="border-b border-line last:border-0">
                    <td className="px-3 py-2.5 text-[12px]">
                      <div className="font-semibold text-ink">{stepLabel(step)}</div>
                      <div className="mt-0.5 text-ink-faint">{step.label}</div>
                    </td>
                    <td className="px-3 py-2.5 text-[12px]">
                      <Badge tone={toneForResult(step.result)}>{step.result}</Badge>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[11px] text-ink-soft">
                      {step.evidenceIds.length ? step.evidenceIds.join(', ') : 'none'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="mt-4 text-[12px] leading-relaxed text-ink-faint">Observable gate trace unavailable.</p>
      )}

      {/* Adversarial check — the verifier's disposition on this call. */}
      <div className="mt-4">
        <dt className="label">Adversarial check</dt>
        <div className="mt-1">
          <Badge tone={verifierTone}>{t.verifier.status}</Badge>
        </div>
        <TracedClaimList claims={t.verifier.claims ?? []} />
      </div>

      <dl className="mt-4 space-y-3 text-[13px]">
        <div>
          <dt className="label">STR and goAML gate</dt>
          <dd className="mt-1 text-ink-soft">{goamlDefense(alert)}</dd>
        </div>
        <div>
          <dt className="label">Audit replay</dt>
          <dd className="mt-1 font-mono text-[12px] text-ink-soft">{auditSummary(auditEntries)}</dd>
        </div>
      </dl>

      {trace && (
        <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">{trace.nonClaims[0]}</p>
      )}
    </section>
  )
}
