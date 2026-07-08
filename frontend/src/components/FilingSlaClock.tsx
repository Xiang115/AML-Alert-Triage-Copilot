import { useEffect, useState } from 'react'
import type { FilingSla } from '../types'
import { Badge } from './ui/Badge'

// STR filing-SLA clock (ADR-0016). Malaysia (BNM) requires an STR the next working day from
// when the compliance officer establishes suspicion — in the console, the analyst's escalate
// decision. States: notApplicable (dismissed — no obligation) · prospective (pending escalate
// recommendation — "if escalated, due by …") · active (escalated, live countdown) · overdue.
// The deadline is the end of the due working day in GMT+8; the countdown ticks client-side and
// flips to overdue on its own, so it stays honest without a server round-trip.

const GMT8 = '+08:00'

function endOfDueBy(dueBy: string): number {
  return new Date(`${dueBy}T23:59:59${GMT8}`).getTime()
}

function fmtDueDate(dueBy: string): string {
  return new Date(`${dueBy}T00:00:00${GMT8}`).toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function fmtRemaining(ms: number): string {
  const totalMin = Math.floor(ms / 60000)
  const d = Math.floor(totalMin / (60 * 24))
  const h = Math.floor((totalMin % (60 * 24)) / 60)
  const m = totalMin % 60
  if (d > 0) return `${d}d ${h}h left`
  if (h > 0) return `${h}h ${m}m left`
  return `${m}m left`
}

export function FilingSlaClock({ sla }: { sla: FilingSla }) {
  const live = sla.applicable && sla.dueBy != null && sla.state !== 'prospective'
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!live) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [live])

  // No filing obligation (dismiss) — a quiet, honest line rather than a countdown.
  if (!sla.applicable) {
    return (
      <section className="rounded-lg border border-line bg-surface px-5 py-4">
        <div className="flex items-center justify-between">
          <h3 className="label">STR filing SLA</h3>
          <Badge tone="bg-line text-ink-soft">N/A</Badge>
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
          No STR filing obligation — a report is filed only on escalation.
        </p>
      </section>
    )
  }

  // Prospective — the analyst has not yet established suspicion (not adjudicated).
  if (sla.state === 'prospective') {
    return (
      <section className="rounded-lg border border-line bg-surface px-5 py-4">
        <div className="flex items-center justify-between">
          <h3 className="label">STR filing SLA</h3>
          <Badge tone="bg-flag-soft text-flag">Prospective</Badge>
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
          If escalated, the STR is due by{' '}
          <span className="font-medium text-ink">{sla.dueBy ? fmtDueDate(sla.dueBy) : '—'}</span>{' '}
          (the next working day).
        </p>
        <p className="mt-2 text-[11px] leading-snug text-ink-faint">{sla.citation}</p>
      </section>
    )
  }

  // Active / overdue — a live countdown to the end of the due working day.
  const ms = sla.dueBy ? endOfDueBy(sla.dueBy) - now : 0
  const overdue = ms <= 0
  const urgent = !overdue && ms < 4 * 60 * 60 * 1000 // < 4h reads as urgent

  const tone = overdue || urgent ? 'border-escalate bg-escalate-soft' : 'border-flag bg-flag-soft'
  const accent = overdue || urgent ? 'text-escalate' : 'text-flag'
  const established = sla.establishedAt ? new Date(sla.establishedAt).toLocaleString() : null

  return (
    <section className={`rounded-lg border ${tone} px-5 py-4`}>
      <div className="flex items-center justify-between">
        <h3 className="label">STR filing SLA</h3>
        <Badge tone={overdue ? 'bg-escalate-soft text-escalate' : 'bg-flag-soft text-flag'}>
          {overdue ? 'Overdue' : 'Due'}
        </Badge>
      </div>

      <div className="mt-1.5 flex items-baseline gap-2">
        <span className={`font-mono text-lg font-semibold tabular-nums ${accent}`}>
          {overdue ? 'Overdue' : sla.dueBy ? fmtRemaining(ms) : '—'}
        </span>
        <span className="text-[13px] text-ink-soft">
          due {sla.dueBy ? fmtDueDate(sla.dueBy) : '—'}
        </span>
      </div>

      {established ? (
        <p className="mt-1 text-[12px] text-ink-soft">Suspicion established {established}</p>
      ) : null}
      <p className="mt-2 text-[11px] leading-snug text-ink-faint">{sla.citation}</p>
    </section>
  )
}
