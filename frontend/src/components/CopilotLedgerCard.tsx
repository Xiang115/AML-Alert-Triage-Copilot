import type { CopilotRunLedger, CopilotRunSummary } from '../types'
import { Badge } from './ui/Badge'

function statusTone(status: CopilotRunLedger['status']): string {
  if (status === 'completed' || status === 'reconstructed') return 'bg-verified-soft text-verified'
  if (status === 'fallback') return 'bg-flag-soft text-flag'
  return 'bg-paper text-ink-soft'
}

export function CopilotLedgerCard({
  runs,
  ledger,
}: {
  runs: CopilotRunSummary[]
  ledger: CopilotRunLedger | null
}) {
  if (!ledger) {
    return (
      <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Copilot run ledger</h3>
        <p className="mt-2 text-[13px] text-ink-faint">Prompt/response ledger unavailable.</p>
      </section>
    )
  }

  const validCalls = ledger.llmCalls.filter((call) => call.schemaValid).length
  const totalMessages = ledger.llmCalls.reduce((sum, call) => sum + call.messages.length, 0)

  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="label">Copilot run ledger</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
            Redacted prompt/response envelope, schema validation, and deterministic controls.
          </p>
        </div>
        <Badge tone={statusTone(ledger.status)}>{ledger.status}</Badge>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 text-[12px]">
        <div>
          <dt className="label">Mode</dt>
          <dd className="mt-1 font-semibold text-ink">{ledger.mode}</dd>
        </div>
        <div>
          <dt className="label">Provider</dt>
          <dd className="mt-1 text-ink">{ledger.provider}</dd>
        </div>
        <div>
          <dt className="label">Runs</dt>
          <dd className="mt-1 font-mono text-ink">{runs.length}</dd>
        </div>
      </dl>

      <div className="mt-4 rounded-md border border-line bg-paper px-3 py-2">
        <div className="label">Capture boundary</div>
        <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{ledger.nonClaims[0]}</p>
      </div>

      <div className="mt-4 overflow-hidden rounded-md border border-line">
        <table className="w-full border-collapse text-left">
          <thead className="bg-paper">
            <tr className="border-b border-line">
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Stage</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Validation</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Hash</th>
            </tr>
          </thead>
          <tbody>
            {ledger.llmCalls.map((call) => (
              <tr key={`${call.stage}-${call.attempt}`} className="border-b border-line last:border-0">
                <td className="px-3 py-2.5 text-[12px]">
                  <div className="font-semibold text-ink">{call.stage}</div>
                  <div className="mt-0.5 text-ink-faint">{call.templateId} / {call.model}</div>
                </td>
                <td className="px-3 py-2.5 text-[12px]">
                  <Badge tone={call.schemaValid ? 'bg-verified-soft text-verified' : 'bg-flag-soft text-flag'}>
                    {call.schemaValid ? 'schema valid' : 'schema failed'}
                  </Badge>
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-ink-soft">
                  {call.rawResponseHash.slice(0, 20)}...
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
        {validCalls}/{ledger.llmCalls.length} model response(s) schema-valid / {totalMessages} captured message(s) / {ledger.deterministicEvents.length} deterministic event(s).
      </p>
    </section>
  )
}
