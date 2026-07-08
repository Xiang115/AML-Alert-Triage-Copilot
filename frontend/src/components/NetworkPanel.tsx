import { useEffect, useState } from 'react'
import { getNetwork } from '../api'
import type { MuleNetwork, NetworkNode, NetworkRole } from '../types'

// Fixed coordinate space the extractor lays nodes out in (ADR-0003 — frozen coords).
const VIEW_W = 800
const VIEW_H = 520

const ROLE_STYLE: Record<NetworkRole, { chip: string; label: string }> = {
  hub: { chip: 'border-ink bg-ink text-paper', label: 'Consolidation hub' },
  mule: { chip: 'border-escalate bg-escalate-soft text-escalate', label: 'Mule' },
  hidden_mule: { chip: 'border-flag bg-flag-soft text-flag ring-2 ring-flag/40', label: 'Hidden mule' },
  benign_cleared: { chip: 'border-verified bg-verified-soft text-verified', label: 'Cleared — legitimate' },
  beneficiary: { chip: 'border-line bg-surface text-ink-soft', label: 'Beneficiary' },
}

function pct(v: number, span: number) {
  return `${(v / span) * 100}%`
}

/** The Mule Network graph (ADR-0009/0015): edges in an SVG layer, accounts as positioned chips
 * over it. Pure/presentational so it renders identically from the frozen fixture or the endpoint. */
export function NetworkPanel({ network }: { network: MuleNetwork }) {
  const byId = new Map(network.nodes.map((n) => [n.accountId, n]))
  const hiddenMules = network.nodes.filter((n) => n.role === 'hidden_mule')
  const benignCleared = network.nodes.filter((n) => n.role === 'benign_cleared')
  const hubs = network.nodes.filter((n) => n.role === 'hub')

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Mule network — {network.typology.name}</h3>
        <span className="rounded-full bg-flag-soft px-2.5 py-1 text-[11px] font-medium text-flag">
          {hiddenMules.length} hidden mule recovered
        </span>
      </div>

      <div className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="label">Recall defense</div>
        <p className="mt-1.5 text-[12px] leading-relaxed text-ink-soft">
          Single-alert triage has a recall ceiling: one account can look ordinary until the shared
          consolidation hub is visible. This network re-surfaces{' '}
          <strong className="text-flag">{hiddenMules.length} hidden mule</strong>, keeps{' '}
          <strong className="text-verified">{benignCleared.length} benign neighbour</strong> cleared,
          and anchors the structure on <strong className="text-ink">{hubs.length} consolidation hub</strong>.
        </p>
        <p className="mt-1.5 text-[11px] leading-relaxed text-ink-faint">
          Boundary: the graph is an investigative defense layer shown qualitatively; the headline measured
          numbers remain the held-out SAML-D triage metrics.
        </p>
      </div>

      {/* Graph canvas: fixed 800×520 aspect so the frozen coords never distort. */}
      <div className="relative mt-4 w-full" style={{ paddingBottom: `${(VIEW_H / VIEW_W) * 100}%` }}>
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          role="presentation"
        >
          {network.edges.map((e) => {
            const from = byId.get(e.fromAccountId)
            const to = byId.get(e.toAccountId)
            if (!from || !to) return null
            return (
              <line
                key={`${e.fromAccountId}-${e.toAccountId}`}
                x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={e.laundering ? '#d1544e' : '#b7bcc4'}
                strokeWidth={e.laundering ? 2.4 : 1.6}
                strokeDasharray={e.laundering ? undefined : '5 4'}
              />
            )
          })}
        </svg>

        {network.nodes.map((n) => (
          <NodeChip key={n.accountId} node={n} />
        ))}
      </div>

      <p className="mt-4 text-[13px] leading-relaxed text-ink-soft">{network.narrative}</p>

      {/* Honesty caption (ADR-0015): the payload carries it so it can't be dropped. */}
      <p className="mt-3 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-faint">
        {network.source}
      </p>
    </section>
  )
}

function NodeChip({ node }: { node: NetworkNode }) {
  const s = ROLE_STYLE[node.role]
  const frac =
    node.totalLegs && node.launderingLegs != null
      ? ` · ${node.launderingLegs}/${node.totalLegs} laundering`
      : ''
  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{ left: pct(node.x, VIEW_W), top: pct(node.y, VIEW_H) }}
      title={node.note ?? undefined}
    >
      <div className={`whitespace-nowrap rounded-md border px-2.5 py-1 text-[11px] font-medium shadow-sm ${s.chip}`}>
        {node.holderName}
        {node.isSeed && <span className="ml-1 opacity-80">◆</span>}
      </div>
      <div className="mt-0.5 text-center text-[10px] text-ink-faint">
        {s.label}{frac}
      </div>
    </div>
  )
}

/** Fetches the seed alert's network and gates it behind a deliberate "reveal" (the demo beat:
 * the analyst judged the account benign; revealing the network exposes the hidden mule). Renders
 * nothing when the alert has no network — which is every alert except the crafted hero. */
export function NetworkReveal({ alertId }: { alertId: string }) {
  const [networkState, setNetworkState] = useState<{ alertId: string; network: MuleNetwork | null } | null>(null)
  const [openAlertId, setOpenAlertId] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    getNetwork(alertId).then((n) => { if (live) setNetworkState({ alertId, network: n }) })
    return () => { live = false }
  }, [alertId])

  const network = networkState?.alertId === alertId ? networkState.network : null
  const open = openAlertId === alertId

  if (!network) return null

  if (!open) {
    return (
      <section className="rounded-lg border border-flag/40 bg-flag-soft/40 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-[14px] font-semibold text-ink">This account isn&rsquo;t alone</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
              Account-level triage saw an ordinary account. Related-account analysis found it wired into a
              consolidation network.
            </p>
          </div>
          <button
            onClick={() => setOpenAlertId(alertId)}
            className="shrink-0 rounded-md border border-flag bg-flag px-3 py-1.5 text-[12px] font-medium text-paper hover:opacity-90"
          >
            Reveal network
          </button>
        </div>
      </section>
    )
  }

  return <NetworkPanel network={network} />
}
