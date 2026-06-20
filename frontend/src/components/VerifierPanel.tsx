import type { Verifier } from '../types'
import { Badge } from './ui/Badge'

interface VerifierPanelProps {
  verifier: Verifier
}

export function VerifierPanel({ verifier }: VerifierPanelProps) {
  const flagged = verifier.status === 'flagged'

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="label">Adversarial QA verifier</h3>
        <Badge tone={flagged ? 'bg-flag-soft text-flag' : 'bg-verified-soft text-verified'}>
          {verifier.status}
        </Badge>
      </div>

      {flagged ? (
        <div className="mt-4 border-l-2 border-flag pl-4">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-flag">Distinguishing test alert</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink">{verifier.note}</p>
          <p className="mt-2 text-[12px] text-ink-soft">
            Confidence capped below threshold (0.60). Manual override required to finalize.
          </p>
        </div>
      ) : (
        <div className="mt-4 border-l-2 border-verified pl-4">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-verified">Triage call verified</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{verifier.note}</p>
        </div>
      )}
    </section>
  )
}
