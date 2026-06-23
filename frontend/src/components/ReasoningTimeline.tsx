import type { ReasoningEvent } from '../hooks/useReasoningPlayback'

interface ReasoningTimelineProps {
  events: ReasoningEvent[]
  revealed: number
  playing: boolean
}

const toneClass: Record<string, string> = {
  escalate: 'text-escalate',
  flag: 'text-flag',
  verified: 'text-verified',
}

/** The agent's reasoning unfolding step-by-step (driven by useReasoningPlayback). */
export function ReasoningTimeline({ events, revealed, playing }: ReasoningTimelineProps) {
  const shown = events.slice(0, revealed)

  return (
    <div className="mt-4">
      <div className="label mb-3 flex items-center gap-2">
        Agent reasoning
        {playing && (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-line-strong border-t-ink" />
        )}
      </div>

      <ol className="space-y-2">
        {shown.map((e, i) => {
          if (e.kind === 'indicator') {
            return (
              <li key={i} className="ml-[26px] flex items-start gap-2 text-[13px] leading-snug">
                <span
                  aria-hidden
                  className={`mt-px shrink-0 font-mono text-[12px] ${e.fired ? 'text-escalate' : 'text-ink-faint'}`}
                >
                  {e.fired ? '✓' : '○'}
                </span>
                <span className={e.fired ? 'text-ink' : 'text-ink-faint line-through decoration-line'}>
                  {e.text}
                </span>
              </li>
            )
          }

          const isFrontier = i === revealed - 1 && playing
          return (
            <li key={i} className="flex items-start gap-2.5">
              <span className="mt-0.5 shrink-0">
                {isFrontier ? (
                  <span className="block h-3.5 w-3.5 animate-spin rounded-full border-2 border-line-strong border-t-ink" />
                ) : (
                  <span className="block font-mono text-[13px] text-verified">✓</span>
                )}
              </span>
              <div>
                <div className="text-[13px] font-medium text-ink">{e.label}</div>
                <div className={`mt-0.5 text-[13px] leading-relaxed ${e.tone ? toneClass[e.tone] : 'text-ink-soft'}`}>
                  {e.detail}
                </div>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
