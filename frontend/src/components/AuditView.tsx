import { useEffect, useState } from 'react'
import type { AuditEntry } from '../types'
import { getAudit } from '../api'
import { Badge } from './ui/Badge'

// The accountability record: every analyst decision and goAML filing, newest first.
// A decision row pairs the AI's call with the human disposition; a submission row
// records the FIU reference the STR was filed under.
export function AuditView() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getAudit()
      .then((e) => active && setEntries(e))
      .catch((err) => console.error(err))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])

  return (
    <div className="h-full overflow-y-auto bg-paper p-6">
      <h2 className="text-xl font-semibold tracking-tight text-ink">Audit trail</h2>
      <p className="mt-1 text-[13px] text-ink-soft">
        Every analyst decision and goAML filing, newest first — the accountability record a regulator can replay.
      </p>

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
                  ) : (
                    <span className="text-ink-faint">—</span>
                  )}
                </td>
                <td className="py-2.5 text-ink-soft">
                  {e.event === 'submission'
                    ? <span className="font-mono text-[12px]">{e.submissionRef}</span>
                    : (e.note ?? <span className="text-ink-faint">—</span>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
