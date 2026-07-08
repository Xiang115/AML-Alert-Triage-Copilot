import type { ReactNode } from 'react'
import type { AccountActivityProfile as Profile, Screening } from '../types'
import { Badge } from './ui/Badge'

// Account Activity Profile (ADR-0016) — a ledger-derived summary of one alert's account
// window. NOT a KYC profile: SAML-D carries no customer identity, so every tile is computed
// from the real ledger (turnover, balance sweep, cross-border/cash exposure, concentration).
// Sits at the top of the right rail so it fills the panel on dismiss alerts too. Colour is
// reserved for the money-laundering tells (a balance swept to ~0, cross-border, cash).

const money = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })
const pct = (share: number) => `${Math.round(share * 100)}%`

function Tile({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-paper px-3 py-2.5">
      <div className="label">{label}</div>
      <div className="mt-1 font-mono text-[13px] tabular-nums text-ink">{value}</div>
      {note ? <div className="mt-0.5 text-[11px] leading-snug text-ink-faint">{note}</div> : null}
    </div>
  )
}

export function AccountActivityProfile({
  profile,
  screening,
}: {
  profile: Profile
  screening?: Screening | null
}) {
  const { turnover, balanceSwept, crossBorder, cash, concentration } = profile
  const primary = turnover[0]
  const extraCcy = turnover.length - 1

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="label">Account activity</h3>
        <span className="text-[11px] text-ink-faint">ledger-derived</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2.5">
        {/* Turnover — grouped per currency (never summed across) */}
        <Tile
          label={primary ? `Turnover · ${primary.currency}` : 'Turnover'}
          value={
            primary ? (
              <>
                <div>in {money(primary.inbound)}</div>
                <div>out {money(primary.outbound)}</div>
              </>
            ) : (
              '—'
            )
          }
          note={
            primary
              ? `net ${primary.net >= 0 ? '+' : ''}${money(primary.net)}${
                  extraCcy > 0 ? ` · +${extraCcy} more ccy` : ''
                }`
              : undefined
          }
        />

        {/* Balance sweep — the pass-through/mule tell (reconstructed running balance) */}
        <Tile
          label="Balance"
          value={
            <span className={balanceSwept.sweptToNearZero ? 'text-escalate' : undefined}>
              {money(balanceSwept.peak)} → {money(balanceSwept.low)}
            </span>
          }
          note={
            balanceSwept.sweptToNearZero ? (
              <span className="text-escalate">swept to ~0 · reconstructed</span>
            ) : (
              `closing ${money(balanceSwept.closing)} · reconstructed`
            )
          }
        />

        {/* Cross-border exposure — real counterparty bank locations */}
        <Tile
          label="Cross-border"
          value={
            crossBorder.total ? (
              <span className={crossBorder.legs > 0 ? 'text-flag' : undefined}>
                {pct(crossBorder.share)}
              </span>
            ) : (
              '—'
            )
          }
          note={`${crossBorder.jurisdictions} jurisdiction${
            crossBorder.jurisdictions === 1 ? '' : 's'
          } · ${crossBorder.legs}/${crossBorder.total} legs`}
        />

        {/* Cash intensity */}
        <Tile
          label="Cash intensity"
          value={
            <span className={cash.legs > 0 ? 'text-flag' : undefined}>{pct(cash.share)}</span>
          }
          note={`${cash.legs}/${cash.total} legs`}
        />

        {/* Counterparty concentration — leg share (well-defined across mixed currencies) */}
        <Tile
          label="Top counterparty"
          value={<span className="font-sans text-ink">{concentration.topCounterparty ?? '—'}</span>}
          note={`${pct(concentration.topShare)} of legs · ${
            concentration.distinctCounterparties
          } counterpart${concentration.distinctCounterparties === 1 ? 'y' : 'ies'}`}
        />

        {/* Sanctions/PEP screening — rollup of the left-rail panel, next to the decision */}
        <Tile
          label="Screening"
          value={
            screening ? (
              <Badge
                tone={
                  screening.blocked
                    ? 'bg-flag-soft text-flag'
                    : 'bg-verified-soft text-verified'
                }
              >
                {screening.blocked ? 'Match' : 'Clear'}
              </Badge>
            ) : (
              '—'
            )
          }
          note={
            screening
              ? `${screening.screenedCounterparties} counterpart${
                  screening.screenedCounterparties === 1 ? 'y' : 'ies'
                }`
              : 'not screened'
          }
        />
      </div>
    </section>
  )
}
