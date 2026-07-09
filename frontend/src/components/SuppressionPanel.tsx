import type { Routing, Suppression } from '../types'

function formatClearedAt(clearedAt: string) {
  const parsed = new Date(clearedAt)
  return Number.isNaN(parsed.getTime()) ? clearedAt : parsed.toLocaleString()
}

export function SuppressionPanel({ data, routing }: { data?: Suppression | null; routing?: Routing | null }) {
  if (!data) return null

  // Network Revocation (ADR-0021): the Mule Network flagged the cleared counterparty as a
  // consolidation hub, so the clearance is cancelled and the alert routes to a human. A distinct
  // alarm state — the network policing the memory — never the benign amber "auto-suppressed".
  if (data.status === 'revoked') {
    return (
      <section className="rounded-lg border border-rose-300 bg-rose-50 p-4">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-[14px] font-semibold text-rose-900">
            Suppression revoked — counterparty is a mule-network consolidation hub
          </h4>
          {data.revokedNetworkId && (
            <span className="shrink-0 rounded bg-rose-200 px-2 py-0.5 text-[11px] font-medium text-rose-900">
              network {data.revokedNetworkId}
            </span>
          )}
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-rose-900/90">{data.rationale}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-rose-800">
          <span className="font-mono">{data.signature}</span>
          <span>routed to human review — the network polices the memory</span>
        </div>
      </section>
    )
  }

  // "Auto-suppressed" is only honest when the control plane actually auto-cleared the alert. A
  // matched benign pattern whose alert is still routed to a human (e.g. an adversarial debate is
  // holding it) matched the memory but was NOT acted on — say so rather than overclaim.
  const autoCleared = routing === 'autoCleared'

  return (
    <section className="rounded-lg border border-amber-300 bg-amber-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-[14px] font-semibold text-amber-900">
          {autoCleared
            ? 'Auto-suppressed — matches a previously cleared pattern'
            : 'Matches a previously cleared pattern — held for review'}
        </h4>
        <span className="shrink-0 rounded bg-amber-200 px-2 py-0.5 text-[11px] font-medium text-amber-900">
          cleared ×{data.clearedCount}
        </span>
      </div>

      <p className="mt-1.5 text-[13px] leading-relaxed text-amber-900/90">{data.rationale}</p>
      {!autoCleared && (
        <p className="mt-1.5 text-[12px] leading-relaxed text-amber-800">
          The learned memory recognised this benign pattern, but another control is still holding the
          alert for a human — suppression did not clear it.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-amber-800">
        <span className="font-mono">{data.signature}</span>
        <span>
          cites decision{' '}
          <a className="font-medium underline underline-offset-2" href={`#/alerts/${data.sourceDecisionId}`}>
            {data.sourceDecisionId}
          </a>
        </span>
        <span>{formatClearedAt(data.clearedAt)}</span>
      </div>
    </section>
  )
}
