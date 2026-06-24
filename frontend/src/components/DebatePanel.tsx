import type { Debate, ReverdictOutcome } from '../types'
import { Badge } from './ui/Badge'

// How each re-verdict outcome is signalled (ADR-0011): a held flag stays a warning, a
// resolved flag reads verified, and a conceded flip is an escalate-toned change of call.
const OUTCOME: Record<ReverdictOutcome, { label: string; badge: string; accent: string; heading: string }> = {
  holds: { label: 'Flag holds — human review', badge: 'bg-flag-soft text-flag', accent: 'border-flag', heading: 'text-flag' },
  convinced: { label: 'Flag resolved', badge: 'bg-verified-soft text-verified', accent: 'border-verified', heading: 'text-verified' },
  conceded: { label: 'Disposition changed', badge: 'bg-escalate-soft text-escalate', accent: 'border-escalate', heading: 'text-escalate' },
}

/** The adversarial debate (ADR-0011): the verifier's challenge, triage's rebuttal, and the
 * re-verdict — shown only when the verifier's first pass flagged the call. */
export function DebatePanel({ debate }: { debate: Debate }) {
  const { challenge, rebuttal, reverdict } = debate
  const o = OUTCOME[reverdict.outcome]
  const rebuttalAccent = rebuttal.conceded ? 'border-verified' : 'border-escalate'
  const rebuttalHeading = rebuttal.conceded ? 'text-verified' : 'text-escalate'

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="label">Adversarial debate</h3>
        <Badge tone={o.badge}>{o.label}</Badge>
      </div>

      <ol className="mt-4 space-y-4">
        <li className="border-l-2 border-flag pl-4">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-flag">Verifier&rsquo;s challenge</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink">{challenge.counterHypothesis}</p>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{challenge.distinguishingTestAssessment}</p>
        </li>

        <li className={`border-l-2 pl-4 ${rebuttalAccent}`}>
          <div className={`text-[12px] font-semibold uppercase tracking-wide ${rebuttalHeading}`}>
            Triage rebuttal{rebuttal.conceded ? ' — conceded' : ''}
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink">{rebuttal.argument}</p>
        </li>

        <li className={`border-l-2 pl-4 ${o.accent}`}>
          <div className={`text-[12px] font-semibold uppercase tracking-wide ${o.heading}`}>Verifier re-verdict</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink">{reverdict.note}</p>
        </li>
      </ol>
    </section>
  )
}
