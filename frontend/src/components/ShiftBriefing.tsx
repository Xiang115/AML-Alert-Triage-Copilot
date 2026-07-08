import type { BlockedReason, GovernanceThresholds, Metrics, QueueNextAction, ShiftBriefing } from '../types'
import { AutoClearDefense } from './AutoClearDefense'

// The queue's routing lanes (ADR-0010). `all` is the union; needsReview/autoCleared are the
// Queue Agent's two lanes; `qaSample` (ADR-0019) is the risk-weighted human-QA slice of the
// auto-cleared lane.
export type Lane = 'needsReview' | 'autoCleared' | 'qaSample' | 'all'

interface ShiftBriefingBannerProps {
  briefing: ShiftBriefing | null
  lane: Lane
  onLaneChange: (lane: Lane) => void
  // Count of auto-cleared alerts sampled for QA spot-check (ADR-0019), from the loaded queue.
  qaSampleCount: number
  // Alerts removed from primary review because an analyst-taught suppression matched.
  learningImpactCount: number
  metrics: Metrics | null
  thresholds: GovernanceThresholds | null
}

// The Queue Agent's overnight-run summary, shown atop the queue. Its lane chips double
// as the filter: the needsReview inbox, the auto-cleared surface, and the QA sample (ADR-0010/0019).
export function ShiftBriefingBanner({
  briefing,
  lane,
  onLaneChange,
  qaSampleCount,
  learningImpactCount,
  metrics,
  thresholds,
}: ShiftBriefingBannerProps) {
  if (!briefing) return null

  const chips: { id: Lane; label: string; count: number; activeTone: string }[] = [
    { id: 'needsReview', label: 'Needs review', count: briefing.needsReview, activeTone: 'text-flag' },
    { id: 'autoCleared', label: 'Auto-cleared', count: briefing.autoCleared, activeTone: 'text-verified' },
    { id: 'qaSample', label: 'QA sample', count: qaSampleCount, activeTone: 'text-flag' },
    { id: 'all', label: 'All', count: briefing.processed, activeTone: 'text-ink' },
  ]

  return (
    <div className="max-h-[28vh] shrink-0 overflow-y-auto overscroll-contain border-b border-line bg-paper px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1.5">
          <span aria-hidden>🌙</span>
          <span className="label truncate text-ink-soft">Queue Agent · overnight run</span>
        </div>
        <span className="shrink-0 font-mono text-[11px] font-semibold tabular-nums text-ink-soft">
          {briefing.autoCleared}/{briefing.processed} cleared
        </span>
      </div>
      <p className="mt-1 max-h-8 overflow-hidden text-[11px] leading-4 text-ink-soft" title={briefing.summary}>
        {briefing.summary}
      </p>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
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
      <NextActionPlan actions={briefing.nextActions} onLaneChange={onLaneChange} />
      <LearningImpactCard count={learningImpactCount} onLaneChange={onLaneChange} />
      <BlockedReasonBreakdown reasons={briefing.blockedReasons} needsReview={briefing.needsReview} />
      <AutoClearDefense metrics={metrics} thresholds={thresholds} qaSampleCount={qaSampleCount} />
    </div>
  )
}

function LearningImpactCard({
  count,
  onLaneChange,
}: {
  count: number
  onLaneChange: (lane: Lane) => void
}) {
  return (
    <section className="mt-2 rounded-md border border-line bg-surface p-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Learning loop impact</h3>
        <div className="shrink-0 font-mono text-[12px] font-semibold tabular-nums text-verified">
          {count}
        </div>
      </div>
      <p className="mt-1 text-[11px] leading-4 text-ink-soft">
        Future look-alikes removed from primary review by analyst-taught suppression.
      </p>
      <button
        type="button"
        onClick={() => onLaneChange('autoCleared')}
        className="mt-2 w-full rounded border border-line bg-paper px-2 py-1 text-left text-[11px] font-medium text-ink-soft hover:border-line-strong hover:text-ink"
      >
        Inspect learned auto-clears
      </button>
    </section>
  )
}

function NextActionPlan({
  actions,
  onLaneChange,
}: {
  actions: QueueNextAction[]
  onLaneChange: (lane: Lane) => void
}) {
  if (!actions.length) return null

  return (
    <section className="mt-2 rounded-md border border-line bg-surface p-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Next operating moves</h3>
        <span className="shrink-0 text-[10px] font-semibold uppercase text-ink-faint">agent plan</span>
      </div>
      <div className="mt-2 space-y-1.5">
        {actions.map((action) => (
          <button
            key={`${action.priority}-${action.label}`}
            onClick={() => onLaneChange(action.lane)}
            className="grid w-full grid-cols-[auto_1fr_auto] gap-2 rounded border border-line bg-paper px-2 py-1 text-left hover:border-line-strong"
            title={action.rationale}
          >
            <span className="font-mono text-[11px] text-ink-faint">{action.priority}</span>
            <span className="min-w-0">
              <span className="block truncate text-[12px] font-medium text-ink">{action.label}</span>
              <span className="block truncate text-[10px] text-ink-faint">{action.rationale}</span>
            </span>
            <span className="font-mono text-[12px] font-semibold tabular-nums text-flag">{action.count}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

function BlockedReasonBreakdown({
  reasons,
  needsReview,
}: {
  reasons: BlockedReason[]
  needsReview: number
}) {
  if (!reasons.length) return null
  const total = reasons.reduce((sum, r) => sum + r.count, 0)

  return (
    <section className="mt-2 rounded-md border border-line bg-surface p-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Blocked from auto-clear</h3>
        <div className="shrink-0 font-mono text-[12px] font-semibold tabular-nums text-flag">
          {total}/{needsReview}
        </div>
      </div>

      <div className="mt-2 space-y-1.5" aria-label="Reasons the Queue Agent preserved alerts for human review">
        {reasons.map((reason) => (
          <div
            key={reason.code}
            className="grid w-full grid-cols-[1fr_auto] gap-2 rounded border border-line bg-paper px-2 py-1"
          >
            <div className="min-w-0">
              <div className="truncate text-[12px] font-medium text-ink">{reason.label}</div>
              <div className="truncate text-[10px] text-ink-faint" title={reason.explanation}>
                {reason.explanation}
              </div>
            </div>
            <div className="font-mono text-[12px] font-semibold tabular-nums text-ink">{reason.count}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
