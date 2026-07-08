import type { DecisionTrace, DecisionTraceStep } from '../types'
import { Badge } from './ui/Badge'

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

export function DecisionTraceCard({ trace }: { trace: DecisionTrace | null }) {
  if (!trace) {
    return (
      <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Decision trace</h3>
        <p className="mt-2 text-[13px] text-ink-faint">Observable decision trace unavailable.</p>
      </section>
    )
  }

  const gateSteps = trace.steps.filter((step) => step.step !== 'indicatorEvaluation')
  const fired = trace.steps.filter((step) => step.step === 'indicatorEvaluation' && step.result === 'fired').length
  const totalIndicators = trace.steps.filter((step) => step.step === 'indicatorEvaluation').length

  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="label">Decision trace</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
            Observable system path from stored triage output through deterministic gates.
          </p>
        </div>
        <Badge tone={trace.routing === 'autoCleared' ? 'bg-verified-soft text-verified' : 'bg-flag-soft text-flag'}>
          {trace.routing ?? 'needsReview'}
        </Badge>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 text-[12px]">
        <div>
          <dt className="label">Recommendation</dt>
          <dd className="mt-1 font-semibold text-ink">{trace.currentRecommendation}</dd>
        </div>
        <div>
          <dt className="label">Confidence</dt>
          <dd className="mt-1 font-mono text-ink">{pct(trace.currentConfidence)}</dd>
        </div>
        <div>
          <dt className="label">Indicators</dt>
          <dd className="mt-1 font-mono text-ink">{fired}/{totalIndicators}</dd>
        </div>
      </dl>

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

      <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
        {trace.nonClaims[0]}
      </p>
    </section>
  )
}
