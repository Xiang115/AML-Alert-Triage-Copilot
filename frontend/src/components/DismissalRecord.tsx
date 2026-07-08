import type { Account, AlertStatus, TriageResult } from '../types'
import { Badge } from './ui/Badge'

// Dismissal Record (ADR-0018) — the read-only counterpart to the STR, shown on dismiss alerts in
// the slot the STR editor occupies on escalate. Documents WHY the alert was cleared, assembled
// entirely from real triage data (no fabrication): the AI's assessment, the verifier's
// corroboration, the typology considered-and-ruled-out with its indicator coverage, any prior
// clearance / debate resolution, and the clean screen. Not filed anywhere — the analyst confirms
// it via Approve, and their own note is the DecisionPanel note (already in the audit trail).

const orDash = (v: string) => (v && v !== 'unknown' ? v : '—')

interface Ground {
  label: string
  text: string
}

function clearanceBasis(triage: TriageResult): Ground[] {
  const grounds: Ground[] = []
  for (const c of triage.claims ?? []) grounds.push({ label: 'AI assessment', text: c.text })
  for (const c of triage.verifier?.claims ?? []) grounds.push({ label: 'Verifier', text: c.text })
  if (triage.suppression?.rationale)
    grounds.push({ label: 'Prior clearance', text: triage.suppression.rationale })
  if (triage.debate?.reverdict?.note)
    grounds.push({ label: 'Debate resolution', text: triage.debate.reverdict.note })
  if (triage.screening && !triage.screening.blocked) {
    const n = triage.screening.screenedCounterparties
    grounds.push({
      label: 'Screening',
      text: `Sanctions / PEP screening clear — ${n} counterpart${n === 1 ? 'y' : 'ies'} screened, no matches.`,
    })
  }
  return grounds
}

export function DismissalRecord({
  triage,
  subject,
  status,
}: {
  triage: TriageResult
  subject: Account
  status: AlertStatus
}) {
  const typology = triage.matchedTypology
  const considered = typology.code !== 'NONE'
  const cov = triage.indicatorCoverage
  const grounds = clearanceBasis(triage)
  const decided = status !== 'pending'

  return (
    <section className="flex grow flex-col overflow-hidden rounded-lg border border-line bg-surface p-5">
      <div className="flex shrink-0 items-center justify-between">
        <h3 className="label">Dismissal record</h3>
        <Badge tone="bg-verified-soft text-verified">No STR required</Badge>
      </div>

      <div className="mt-4 flex grow flex-col gap-5 overflow-y-auto pr-1">
        {/* Subject — the reviewed account (accountId is the real anchor; SAML-D identity is thin). */}
        <div className="rounded-md border border-line bg-paper px-3 py-2.5">
          <div className="label">Subject</div>
          <div className="mt-1 text-[13px] text-ink">{subject.holderName}</div>
          <div className="mt-0.5 font-mono text-[12px] text-ink-soft">
            {subject.accountId} · {orDash(subject.accountType)} · opened {subject.openedAt.substring(0, 10)}
          </div>
        </div>

        {/* Typology considered + disposition */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="label">Typology considered</div>
            {considered ? (
              <>
                <div className="mt-1 text-[13px] text-ink">
                  {typology.code} — {typology.name}
                </div>
                <div className="mt-1">
                  <Badge tone="bg-paper text-ink-soft">ruled out</Badge>
                </div>
                {cov.indicators.length > 0 && (
                  <div className="mt-1 text-[11px] text-ink-faint">
                    {cov.fired.length} of {cov.indicators.length} indicators fired — below escalation threshold
                  </div>
                )}
              </>
            ) : (
              <div className="mt-1 text-[13px] text-ink-soft">No typology matched the evidence.</div>
            )}
          </div>
          <div>
            <div className="label">Disposition</div>
            <div className="mt-1 text-[13px] text-ink">Dismiss — no report</div>
            <div className="mt-0.5 font-mono text-[12px] text-ink-soft">
              {Math.round(triage.confidence * 100)}% confidence
            </div>
          </div>
        </div>

        {/* Grounds for clearance — the structured, adaptive basis (read-only). */}
        <div>
          <div className="label mb-1.5">Grounds for clearance</div>
          <ul className="space-y-2">
            {grounds.map((g, i) => (
              <li key={i} className="border-l-2 border-line pl-3">
                <div className="text-[11px] font-medium uppercase tracking-wide text-ink-faint">{g.label}</div>
                <p className="mt-0.5 text-[13px] leading-relaxed text-ink">{g.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Closure footer — mirrors the STR's filing footer. The decision endpoint appends an audit
          entry on dismissal, so this is honest before and after the analyst signs off. */}
      <div className="mt-4 shrink-0 border-t border-line pt-4">
        {decided ? (
          <div className="flex items-center gap-1.5 text-[12px] font-medium text-verified">
            <span>✓</span> Recorded to audit trail
          </div>
        ) : (
          <p className="text-[12px] leading-relaxed text-ink-faint">
            Approving records this dismissal — with your note — to the audit trail. No STR is filed.
          </p>
        )}
      </div>
    </section>
  )
}
