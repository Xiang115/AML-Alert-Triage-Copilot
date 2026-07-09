import type { Screening } from '../types'
import { Badge } from './ui/Badge'

interface ScreeningPanelProps {
  data?: Screening | null
}

// Sanctions / PEP screening (Slice B). Renders the deterministic screen of the alert's
// counterparties against the OFAC SDN list.
//
// On real SAML-D data every alert screens clean (counterparties have no real names), so the clear
// state is the common case — it renders as a COMPACT chip, not a full section, so it stops reading
// as a big box where nothing happened. The value it still carries (a deterministic gate that would
// override auto-clear on a hit) stays discoverable in the chip's tooltip.
//
// A blocked result is the rare, high-signal case: it keeps the full fail-safe treatment.
// Returns null only when the record was never screened (a pre-Slice-B alert).
export function ScreeningPanel({ data }: ScreeningPanelProps) {
  if (!data) return null
  const n = data.screenedCounterparties
  const counterparties = `${n} counterpart${n === 1 ? 'y' : 'ies'}`

  if (!data.blocked) {
    return (
      <div
        className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-line bg-surface px-3 py-2 text-[12px]"
        title="Deterministic gate: a sanctions/PEP hit would override routing and hold the alert for a human, even if triage recommends dismiss."
      >
        <Badge tone="bg-verified-soft text-verified">Sanctions / PEP: clear</Badge>
        <span className="text-ink-soft">
          Screened {counterparties}
          {data.citation ? <> against <span className="text-ink">{data.citation}</span></> : null}
        </span>
        <span className="text-ink-faint">· deterministic gate</span>
      </div>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="label">Sanctions / PEP screening</h3>
        <Badge tone="bg-flag-soft text-flag">Match — review required</Badge>
      </div>

      <div className="mt-1.5 text-[12px] text-ink-soft">
        Screened {counterparties}
        {data.citation ? <> against <span className="text-ink">{data.citation}</span></> : null}
      </div>

      <div className="mt-4 space-y-2">
        {data.matches.map((m, i) => (
          <div
            key={i}
            className="rounded border border-flag bg-flag-soft px-3 py-2 font-mono text-[12px] text-ink"
          >
            <span className="text-ink-soft">{m.counterpartyId}</span> → <b>{m.matchedName}</b>
            {' · '}{m.listName}{m.program ? ` (${m.program})` : ''}
            {' · '}{m.matchType} {Math.round(m.score * 100)}%
          </div>
        ))}
        <p className="text-[12px] leading-relaxed text-flag">
          Fail-safe defense: deterministic screening runs outside the LLM and overrides routing. Even
          if triage recommends dismiss, the copilot will not auto-clear a screened counterparty — this
          alert is held for human review.
        </p>
      </div>
    </section>
  )
}
