import type { ShiftBriefing } from '../types'

// The queue's routing lanes (ADR-0010). `all` is the union; the others are the
// Queue Agent's two lanes. Default is the needsReview inbox — the analyst's worklist.
export type Lane = 'needsReview' | 'autoCleared' | 'all'

interface ShiftBriefingBannerProps {
  briefing: ShiftBriefing | null
  lane: Lane
  onLaneChange: (lane: Lane) => void
}

// The Queue Agent's overnight-run summary, shown atop the queue. Its lane chips double
// as the filter: the needsReview inbox vs the auto-cleared QA surface (ADR-0010).
export function ShiftBriefingBanner({ briefing, lane, onLaneChange }: ShiftBriefingBannerProps) {
  if (!briefing) return null

  const chips: { id: Lane; label: string; count: number; activeTone: string }[] = [
    { id: 'needsReview', label: 'Needs review', count: briefing.needsReview, activeTone: 'text-flag' },
    { id: 'autoCleared', label: 'Auto-cleared', count: briefing.autoCleared, activeTone: 'text-verified' },
    { id: 'all', label: 'All', count: briefing.processed, activeTone: 'text-ink' },
  ]

  return (
    <div className="border-b border-line bg-paper px-5 py-3">
      <div className="flex items-center gap-1.5">
        <span aria-hidden>🌙</span>
        <span className="label text-ink-soft">Queue Agent · overnight run</span>
      </div>
      <p className="mt-1.5 text-[12px] leading-snug text-ink-soft">{briefing.summary}</p>
      <div className="mt-2.5 flex gap-1.5">
        {chips.map((c) => {
          const active = lane === c.id
          return (
            <button
              key={c.id}
              onClick={() => onLaneChange(c.id)}
              aria-pressed={active}
              className={`rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${
                active ? 'border-ink bg-surface text-ink' : 'border-line text-ink-faint hover:text-ink-soft'
              }`}
            >
              {c.label}{' '}
              <span className={`font-mono tabular-nums ${active ? c.activeTone : 'text-ink-faint'}`}>{c.count}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
