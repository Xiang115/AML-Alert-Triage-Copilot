import type { TriageResult } from '../types'
import type { ReasoningEvent } from '../hooks/useReasoningPlayback'
import { ReasoningTimeline } from './ReasoningTimeline'

interface TriageCardProps {
  triage: TriageResult
  // Reasoning timeline to render, fed by either the precomputed replay or the live stream.
  timeline: { events: ReasoningEvent[]; revealed: number; playing: boolean }
  onRunLive: () => void
  onReplayReasoning: () => void
  busy: boolean
}

export function TriageCard({ triage, timeline, onRunLive, onReplayReasoning, busy }: TriageCardProps) {
  const escalate = triage.recommendation === 'escalate'
  const flagged = triage.verifier.status === 'flagged'
  // Only a flagged DISMISS is capped below the review line (so it can't auto-clear). A
  // flagged escalate keeps its true coverage — the verifier's disagreement routes it to review.
  const capped = flagged && !escalate
  const pct = Math.round(triage.confidence * 100)
  const { indicators, fired } = triage.indicatorCoverage
  const firedSet = new Set(fired)

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="label">Triage recommendation</h3>
        <div className="flex items-center gap-3">
          <button
            onClick={onReplayReasoning}
            disabled={busy}
            title="Replay the agent's reasoning step-by-step (precomputed — no API call)"
            className="text-[12px] font-medium text-flag underline-offset-4 hover:underline disabled:opacity-50"
          >
            ▶ Reasoning
          </button>
          <button
            onClick={onRunLive}
            disabled={busy}
            title="Stream the live pipeline's reasoning over SSE (real DeepSeek run)"
            className="text-[12px] font-medium text-ink-soft underline-offset-4 hover:text-ink hover:underline disabled:opacity-50"
          >
            Run live
          </button>
        </div>
      </div>

      {timeline.playing || timeline.revealed > 0 ? (
        <ReasoningTimeline events={timeline.events} revealed={timeline.revealed} playing={timeline.playing} />
      ) : (
        <>
          {/* Recommendation + confidence */}
          <div className="mt-4 flex items-end justify-between gap-6">
            <div>
              <div className={`text-2xl font-semibold tracking-tight ${escalate ? 'text-escalate' : 'text-verified'}`}>
                {escalate ? 'Escalate' : 'Dismiss'}
              </div>
            </div>
            <div className="grow">
              <div className="mb-1 flex items-baseline justify-between">
                <span className="label">Confidence{capped ? ' · capped' : ''}</span>
                <span className={`font-mono text-[13px] font-medium tabular-nums ${capped ? 'text-flag' : 'text-ink'}`}>{pct}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
                <div className={`h-full rounded-full ${capped ? 'bg-flag' : 'bg-ink'}`} style={{ width: `${pct}%` }}></div>
              </div>
              {flagged && (
                <p className="mt-1.5 text-[12px] leading-snug text-flag">
                  {escalate
                    ? 'All typology indicators present — the independent verifier disagrees and routes this to human review.'
                    : 'Capped below the review line by the verifier’s flag, so it can’t auto-clear — human review.'}
                </p>
              )}
            </div>
          </div>

          {/* Indicator coverage — the evidence behind the confidence number (ADR-0007).
              The score is the fraction of the typology's red flags that fired, not a
              figure the model invented. */}
          {indicators.length > 0 && (
            <div className="mt-5 border-t border-line pt-4">
              <div className="flex items-baseline justify-between">
                <span className="label">Indicator coverage</span>
                <span className="font-mono text-[12px] tabular-nums text-ink-soft">
                  {fired.length}/{indicators.length} fired
                </span>
              </div>
              <ul className="mt-2.5 space-y-1.5">
                {indicators.map((ind) => {
                  const hit = firedSet.has(ind)
                  return (
                    <li key={ind} className="flex items-start gap-2 text-[13px] leading-snug">
                      <span
                        aria-hidden
                        className={`mt-px shrink-0 font-mono text-[12px] ${hit ? 'text-escalate' : 'text-ink-faint'}`}
                      >
                        {hit ? '✓' : '○'}
                      </span>
                      <span className={hit ? 'text-ink' : 'text-ink-faint line-through decoration-line'}>
                        {ind}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}

          {/* Matched typology */}
          <div className="mt-5 border-t border-line pt-4">
            <div className="label">Matched typology</div>
            <div className="mt-1 flex items-baseline justify-between gap-3">
              <span className="text-[14px] font-medium text-ink">
                {triage.matchedTypology.code} — {triage.matchedTypology.name}
              </span>
              <span className="shrink-0 font-mono text-[11px] text-ink-faint">{triage.matchedTypology.source}</span>
            </div>
          </div>

          {/* Explanation */}
          <div className="mt-4">
            <div className="label">Evidence</div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">{triage.explanation}</p>
          </div>
        </>
      )}
    </section>
  )
}
