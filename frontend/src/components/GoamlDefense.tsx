import type { SubmissionAck } from '../types'
import { Badge } from './ui/Badge'

interface GoamlDefenseProps {
  canExport: boolean
  ack: SubmissionAck | null
  onExport: () => void
  citedTransactionCount: number
  anchoredClaimCount: number
  totalClaimCount: number
  pulledClaimCount: number
}

export function GoamlDefense({
  canExport,
  ack,
  onExport,
  citedTransactionCount,
  anchoredClaimCount,
  totalClaimCount,
  pulledClaimCount,
}: GoamlDefenseProps) {
  return (
    <div className="mt-4 shrink-0 border-t border-line pt-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="label">goAML filing defense</h3>
        <Badge tone={ack ? 'bg-verified-soft text-verified' : canExport ? 'bg-paper text-ink-soft' : 'bg-flag-soft text-flag'}>
          {ack ? 'filed' : canExport ? 'unlocked' : 'locked'}
        </Badge>
      </div>

      <ol className="space-y-2 text-[12px] leading-snug">
        <Step
          done={canExport || !!ack}
          label="Human sign-off gate"
          text={canExport || ack ? 'Analyst approved escalation; export is permitted.' : 'Approve this escalation before any STR can leave.'}
        />
        <Step
          done={pulledClaimCount === 0}
          label="Evidence package"
          text={`${citedTransactionCount} cited transaction(s); ${
            totalClaimCount > 0
              ? `${anchoredClaimCount}/${totalClaimCount} STR claim(s) traced to evidence`
              : 'claim tracing unavailable for this draft'
          }${pulledClaimCount ? `; ${pulledClaimCount} untraced claim(s) pulled` : ''}.`}
        />
        <Step
          done
          label="Export validation"
          text="Server blocks unanchored grounds, generates goAML XML, and validates it against the checked-in XSD before return or acknowledgement."
        />
        <Step
          done={!!ack}
          label="Filing and audit"
          text={ack ? `FIU accepted ref ${ack.submissionRef}; submission event recorded to audit.` : 'Filing receipt and audit event are created only after submission.'}
        />
      </ol>

      {ack ? (
        <div className="mt-3 rounded-md border border-verified bg-verified-soft px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-[12px] font-medium text-verified">
            <span>✓</span> Filed to goAML · accepted
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-ink-soft">ref {ack.submissionRef}</div>
        </div>
      ) : canExport ? (
        <button
          onClick={onExport}
          className="mt-3 w-full rounded-md bg-ink px-4 py-2.5 text-[13px] font-medium text-surface transition-opacity hover:opacity-90"
        >
          Export &amp; file goAML STR
        </button>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
          The filing seam is present but locked: no goAML XML can be exported without analyst approval.
        </p>
      )}
    </div>
  )
}

function Step({ done, label, text }: { done: boolean; label: string; text: string }) {
  return (
    <li className="flex gap-2">
      <span className={`mt-0.5 shrink-0 font-mono text-[12px] ${done ? 'text-verified' : 'text-flag'}`}>
        {done ? '✓' : '○'}
      </span>
      <span>
        <span className="font-medium text-ink">{label}: </span>
        <span className="text-ink-soft">{text}</span>
      </span>
    </li>
  )
}
