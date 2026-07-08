import type { GovernanceChangeRequest, GovernanceChangeRequestList } from '../types'

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtValue(value: Record<string, unknown>): string {
  return Object.entries(value)
    .map(([key, v]) => `${key}: ${Array.isArray(v) ? v.join(', ') : String(v)}`)
    .join(' | ')
}

function statusTone(status: GovernanceChangeRequest['status']) {
  if (status === 'approved' || status === 'applied') return 'border-verified bg-verified-soft text-verified'
  if (status === 'rejected' || status === 'rolledBack') return 'border-flag bg-flag-soft text-flag'
  return 'border-line bg-paper text-ink-soft'
}

export function ModelRiskChangeControl({ data }: { data: GovernanceChangeRequestList | null }) {
  if (!data) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Model-risk change control</h3>
        <p className="mt-3 text-[13px] text-ink-faint">Change-control ledger has not loaded yet.</p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Model-risk change control</h3>
        <div className="flex gap-2 text-[11px]">
          <span className="rounded border border-line bg-paper px-2 py-1 font-medium text-ink-soft">{data.pending} pending</span>
          <span className="rounded border border-verified bg-verified-soft px-2 py-1 font-medium text-verified">{data.approved} approved</span>
        </div>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        Threshold, prompt, provider, typology, and suppression changes are proposals until explicit model-risk approvals exist.
      </p>

      {data.blockedReason && (
        <p className="mt-2 rounded-md border border-line bg-paper px-3 py-2 text-[12px] leading-relaxed text-ink-soft">
          {data.blockedReason}
        </p>
      )}

      <div className="mt-4 space-y-3">
        {data.changes.map((change) => (
          <article key={change.changeId} className="rounded-md border border-line bg-paper p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-[13px] font-semibold text-ink">{change.changeId}</h4>
                <p className="mt-1 text-[12px] text-ink-faint">
                  {change.type} | requested by {change.requestedBy} | {fmtDate(change.requestedAt)}
                </p>
              </div>
              <span className={`shrink-0 rounded border px-2 py-1 text-[11px] font-medium ${statusTone(change.status)}`}>
                {change.status}
              </span>
            </div>

            <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{change.rationale}</p>

            <dl className="mt-3 grid gap-2 text-[12px] sm:grid-cols-2">
              <div>
                <dt className="text-ink-faint">Current</dt>
                <dd className="mt-1 font-mono leading-relaxed text-ink">{fmtValue(change.currentValue)}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Proposed</dt>
                <dd className="mt-1 font-mono leading-relaxed text-ink">{fmtValue(change.proposedValue)}</dd>
              </div>
            </dl>

            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-ink-soft">
              {change.requiredApprovals.map((role) => (
                <span key={role} className="rounded border border-line bg-surface px-2 py-1">
                  {role} approval
                </span>
              ))}
            </div>

            <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">Rollback: {change.rollbackPlan}</p>
            <p className="mt-2 font-mono text-[11px] leading-relaxed text-ink-faint">{change.evidence.join(' | ')}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
