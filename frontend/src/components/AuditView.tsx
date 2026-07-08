import { useEffect, useState } from 'react'
import type { AuditEntry, DecisionSummary } from '../types'
import { getAudit, getAuditSummary } from '../api'
import { Badge } from './ui/Badge'

// The accountability record: every analyst decision and goAML filing, newest first.
// A decision row pairs the AI's call with the human disposition; a submission row
// records the FIU reference the STR was filed under.
export function AuditView() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [summary, setSummary] = useState<DecisionSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    Promise.all([getAudit(), getAuditSummary()])
      .then(([e, s]) => { if (active) { setEntries(e); setSummary(s) } })
      .catch((err) => console.error(err))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])

  return (
    <div className="h-full overflow-y-auto bg-paper p-6">
      <h2 className="text-xl font-semibold tracking-tight text-ink">Audit trail</h2>
      <p className="mt-1 text-[13px] text-ink-soft">
        Every Queue Agent auto-clear, adversarial debate, analyst decision, and goAML filing, newest first — the accountability record a regulator can replay.
      </p>

      {/* Session AI–analyst agreement (GET /audit/summary): live this-session activity, NOT a
          held-out performance metric — appears only once the analyst has actually decided. */}
      {summary && summary.decisions > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-1.5 rounded-lg border border-line bg-surface px-4 py-3">
          <span className="label">This session</span>
          <SummaryStat label="decisions" value={summary.decisions} />
          <SummaryStat label="approved" value={summary.approvals} />
          <SummaryStat label="overrides" value={summary.overrides} />
          <span className="ml-auto text-[13px]">
            <span className="text-ink-soft">AI–analyst agreement </span>
            <span className="font-mono font-semibold tabular-nums text-ink">
              {summary.agreementRate === null ? '—' : `${Math.round(summary.agreementRate * 100)}%`}
            </span>
          </span>
        </div>
      )}

      {loading ? (
        <p className="mt-6 text-[13px] text-ink-faint">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="mt-6 text-[13px] text-ink-faint">No decisions recorded yet. Approve or override an alert to start the trail.</p>
      ) : (
        <table className="mt-5 w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="label py-2 pr-4 font-medium">When</th>
              <th className="label py-2 pr-4 font-medium">Alert</th>
              <th className="label py-2 pr-4 font-medium">Event</th>
              <th className="label py-2 pr-4 font-medium">AI → Human</th>
              <th className="label py-2 font-medium">Reason / reference</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={i} className="border-b border-line align-top">
                <td className="py-2.5 pr-4 font-mono text-[12px] text-ink-soft">{e.at.replace('T', ' ').substring(0, 19)}</td>
                <td className="py-2.5 pr-4 font-mono text-[12px] text-ink">{e.alertId}</td>
                <td className="py-2.5 pr-4">
                  {e.event === 'submission' ? (
                    <Badge tone="bg-verified-soft text-verified">Filed</Badge>
                  ) : e.event === 'autoClear' ? (
                    <Badge tone="bg-verified-soft text-verified">Auto-cleared</Badge>
                  ) : e.event === 'debateResolved' ? (
                    <Badge tone="bg-flag-soft text-flag">Debate</Badge>
                  ) : (
                    <Badge tone="bg-paper text-ink-soft">{e.action}</Badge>
                  )}
                </td>
                <td className="py-2.5 pr-4 text-ink">
                  {e.event === 'decision' ? (
                    <span className="font-mono text-[12px]">
                      {e.aiRecommendation} → {e.finalDisposition}
                      {e.aiRecommendation !== e.finalDisposition && (
                        <span className="ml-1.5 text-escalate">override</span>
                      )}
                    </span>
                  ) : e.event === 'autoClear' ? (
                    <span className="font-mono text-[12px] text-verified">{e.aiRecommendation} → auto</span>
                  ) : e.event === 'debateResolved' ? (
                    <span className="font-mono text-[12px] text-flag">{e.aiRecommendation} · debated</span>
                  ) : (
                    <span className="text-ink-faint">—</span>
                  )}
                </td>
                <td className="py-2.5 text-ink-soft">
                  <AuditDefense entry={e} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function AuditDefense({ entry: e }: { entry: AuditEntry }) {
  const actor = e.actorId && e.actorRole ? (
    <div className="font-mono text-[11px] text-ink-faint">actor {e.actorId} ({e.actorRole})</div>
  ) : null

  if (e.event === 'submission') {
    return (
      <div className="text-[12px] leading-relaxed">
        <div className="font-mono text-ink">{e.submissionRef}</div>
        {actor}
        <div>goAML submission accepted; filing acknowledgement preserved in the append-only audit trail.</div>
      </div>
    )
  }

  if (e.event === 'autoClear') {
    return (
      <div className="text-[12px] leading-relaxed">
        <div>
          Auto-Clear Policy · {Math.round((e.confidence ?? 0) * 100)}% · verifier {e.verifierStatus}
        </div>
        <div>Defensible because it was dismiss-only, verifier-agreed, threshold-gated, and audit-recorded.</div>
      </div>
    )
  }

  if (e.event === 'debateResolved') {
    return (
      <div className="text-[12px] leading-relaxed">
        <div>{e.note}</div>
        <div>Defensible because the verifier challenge and resolution are replayable before human action.</div>
      </div>
    )
  }

  if (e.event === 'qaOutcome') {
    return (
      <div className="text-[12px] leading-relaxed">
        <div>{e.note}</div>
        {actor}
        <div>QA review is preserved as feedback into threshold governance, not silent model retraining.</div>
      </div>
    )
  }

  if (e.event === 'decision') {
    const overridden = e.aiRecommendation !== e.finalDisposition
    return (
      <div className="text-[12px] leading-relaxed">
        <div>{e.note ?? <span className="text-ink-faint">No analyst note recorded.</span>}</div>
        {actor}
        <div>
          {overridden
            ? 'Override is accountable: AI call, human disposition, confidence, verifier status, and reason are kept together.'
            : 'Approval is accountable: the human accepted the AI call and the decision is preserved with model context.'}
        </div>
      </div>
    )
  }

  return <span className="text-ink-faint">—</span>
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <span className="text-[13px]">
      <span className="font-mono font-semibold tabular-nums text-ink">{value}</span>
      <span className="ml-1 text-ink-soft">{label}</span>
    </span>
  )
}
