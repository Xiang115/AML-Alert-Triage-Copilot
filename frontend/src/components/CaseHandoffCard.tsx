import type { CaseHandoff } from '../types'
import { Badge } from './ui/Badge'

function statusTone(status: CaseHandoff['caseStatusUpdate']): string {
  if (status === 'filed' || status === 'dismissed' || status === 'autoCleared') {
    return 'bg-verified-soft text-verified'
  }
  if (status === 'escalated') return 'bg-flag-soft text-flag'
  return 'bg-paper text-ink-soft'
}

function writeBackTone(handoff: CaseHandoff): string {
  return handoff.writeBack.allowed
    ? 'bg-verified-soft text-verified'
    : 'bg-paper text-ink-soft'
}

export function CaseHandoffCard({ handoff }: { handoff: CaseHandoff | null }) {
  if (!handoff) {
    return (
      <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Bank handoff</h3>
        <p className="mt-2 text-[13px] text-ink-faint">Case-management packet unavailable.</p>
      </section>
    )
  }

  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="label">Bank handoff</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
            Case-management write-back packet for the bank AML queue.
          </p>
        </div>
        <Badge tone={statusTone(handoff.caseStatusUpdate)}>{handoff.caseStatusUpdate}</Badge>
      </div>

      <dl className="mt-4 space-y-3 text-[13px]">
        <div>
          <dt className="label">Target systems</dt>
          <dd className="mt-1 text-ink-soft">{handoff.targetSystems.join(' / ')}</dd>
        </div>

        <div>
          <dt className="label">Case note</dt>
          <dd className="mt-1 leading-relaxed text-ink-soft">{handoff.caseNote}</dd>
        </div>

        <div>
          <dt className="label">Write-back gate</dt>
          <dd className="mt-1 flex flex-col gap-1 text-ink-soft">
            <span className="flex items-center gap-2">
              <Badge tone={writeBackTone(handoff)}>{handoff.writeBack.mode}</Badge>
              <span>{handoff.writeBack.allowed ? 'Human-approved case update ready.' : handoff.writeBack.blockedReason}</span>
            </span>
            <span className="text-[12px] text-ink-faint">{handoff.writeBack.productionGate}</span>
          </dd>
        </div>

        {handoff.submissionRef && (
          <div>
            <dt className="label">FIU acknowledgement</dt>
            <dd className="mt-1 font-mono text-[12px] text-ink">{handoff.submissionRef}</dd>
          </div>
        )}
      </dl>

      <div className="mt-4 overflow-hidden rounded-md border border-line">
        <table className="w-full border-collapse text-left">
          <thead className="bg-paper">
            <tr className="border-b border-line">
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Artifact</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Endpoint</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">State</th>
            </tr>
          </thead>
          <tbody>
            {handoff.attachments.map((artifact) => (
              <tr key={artifact.endpoint} className="border-b border-line last:border-0">
                <td className="px-3 py-2.5 text-[12px] font-semibold text-ink">{artifact.name}</td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-ink-soft">{artifact.endpoint}</td>
                <td className="px-3 py-2.5 text-[12px]">
                  <span className={artifact.available ? 'font-medium text-verified' : 'font-medium text-ink-faint'}>
                    {artifact.available ? 'attached' : 'locked'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
