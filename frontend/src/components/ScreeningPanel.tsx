import type { Screening } from '../types'
import { Badge } from './ui/Badge'

interface ScreeningPanelProps {
  data?: Screening | null
}

// Sanctions / PEP screening (Slice B). Renders the deterministic screen of the alert's
// counterparties against the OFAC SDN list. A blocked result reads as a fail-safe ("human
// review required"); a clean screen shows the honest positive signal ("screened N — no
// matches"), which is the point on real SAML-D data (counterparties have no real names).
// Returns null only when the record was never screened (a pre-Slice-B alert).
export function ScreeningPanel({ data }: ScreeningPanelProps) {
  if (!data) return null
  const blocked = data.blocked
  const n = data.screenedCounterparties
  const counterparties = `${n} counterpart${n === 1 ? 'y' : 'ies'}`

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="label">Sanctions / PEP screening</h3>
        <Badge tone={blocked ? 'bg-flag-soft text-flag' : 'bg-verified-soft text-verified'}>
          {blocked ? 'Match — review required' : 'Clear'}
        </Badge>
      </div>

      <div className="mt-1.5 text-[12px] text-ink-soft">
        Screened {counterparties}
        {data.citation ? <> against <span className="text-ink">{data.citation}</span></> : null}
      </div>

      {blocked ? (
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
      ) : (
        <div className="mt-4 border-l-2 border-verified pl-4">
          <p className="text-[13px] leading-relaxed text-ink-soft">
            No watchlist matches on this alert’s counterparties.
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-faint">
            Screening is still a deterministic gate: a future hit would override auto-clear and route the
            alert to a human.
          </p>
        </div>
      )}
    </section>
  )
}
