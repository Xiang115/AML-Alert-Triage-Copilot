import type { Alert, AuditEntry, GovernanceThresholds } from '../types'
import { Badge } from './ui/Badge'
import { TracedClaimList } from './TracedClaimList'

interface DefenseCaseProps {
  alert: Alert
  thresholds: GovernanceThresholds | null
  auditEntries: AuditEntry[]
}

const pct = (n: number) => `${Math.round(n * 100)}%`

function routingDefense(alert: Alert, thresholds: GovernanceThresholds | null): string {
  const t = alert.triage
  const autoClearLine = thresholds?.autoClear ?? 0.85
  const reviewLine = thresholds?.review ?? 0.6

  if (t.recommendation === 'escalate') {
    return 'Needs review: escalation is a consequential call and can never be auto-cleared or auto-filed.'
  }
  if (t.debate) {
    return 'Needs review: the agents entered adversarial debate, so the firewall prevents auto-clear.'
  }
  if (t.verifier.status === 'flagged') {
    return 'Needs review: the verifier challenged the dismiss call, so the clear is blocked.'
  }
  if (t.screening?.blocked) {
    return 'Needs review: screening found a counterparty hit or potential hit.'
  }
  if (alert.routing === 'autoCleared' && t.suppression?.status === 'suppressed') {
    return `Auto-cleared by learned suppression: dismiss + verifier agreed + confidence above ${pct(reviewLine)} review line + benign-consistent envelope.`
  }
  if (alert.routing === 'autoCleared' || t.confidence >= autoClearLine) {
    return `Auto-clear eligible: dismiss + verifier agreed + confidence at or above ${pct(autoClearLine)}.`
  }
  return `Needs review: dismiss + verifier agreed, but confidence is below the ${pct(autoClearLine)} auto-clear line.`
}

function goamlDefense(alert: Alert): string {
  if (!alert.triage.strDraft) return 'No STR generated: current disposition is dismiss.'
  if (alert.status === 'pending') return 'STR draft exists, but goAML export is locked until analyst sign-off.'
  return 'goAML export is unlocked after analyst sign-off and remains schema-validated server-side.'
}

function auditSummary(entries: AuditEntry[]): string {
  if (entries.length === 0) return 'No audit event recorded for this alert yet.'
  const counts = entries.reduce<Record<string, number>>((acc, e) => {
    acc[e.event] = (acc[e.event] ?? 0) + 1
    return acc
  }, {})
  return Object.entries(counts)
    .map(([event, count]) => `${event} x${count}`)
    .join(' / ')
}

export function DefenseCase({ alert, thresholds, auditEntries }: DefenseCaseProps) {
  const t = alert.triage
  const fired = t.indicatorCoverage.fired.length
  const total = t.indicatorCoverage.indicators.length
  const cited = t.citedTransactionIds.length
  const verifierTone = t.verifier.status === 'agreed'
    ? 'bg-verified-soft text-verified'
    : 'bg-flag-soft text-flag'
  const routingTone = alert.routing === 'autoCleared'
    ? 'bg-verified-soft text-verified'
    : 'bg-flag-soft text-flag'

  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="label">Defense case</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
            One-page replay of why this alert was routed the way it was.
          </p>
        </div>
        <Badge tone={routingTone}>{alert.routing ?? 'needsReview'}</Badge>
      </div>

      <dl className="mt-4 space-y-3 text-[13px]">
        <div>
          <dt className="label">Evidence basis</dt>
          <dd className="mt-1 text-ink">
            {t.matchedTypology.code} - {t.matchedTypology.name}
            <span className="text-ink-soft"> / {fired}/{total} indicators fired / {cited} cited txns</span>
          </dd>
        </div>

        <div>
          <dt className="label">Adversarial check</dt>
          <dd className="mt-1 flex items-start gap-2 text-ink-soft">
            <Badge tone={verifierTone}>{t.verifier.status}</Badge>
          </dd>
          <TracedClaimList claims={t.verifier.claims ?? []} />
        </div>

        <div>
          <dt className="label">Routing defense</dt>
          <dd className="mt-1 text-ink-soft">{routingDefense(alert, thresholds)}</dd>
        </div>

        {thresholds && (
          <div>
            <dt className="label">Operating point</dt>
            <dd className="mt-1 font-mono text-[12px] text-ink-soft">
              confidence {pct(t.confidence)} / review {pct(thresholds.review)} / auto-clear {pct(thresholds.autoClear)}
              {alert.borderlineDismiss ? ' / borderline dismiss' : ''}
              {alert.qaSampled ? ' / QA sampled' : ''}
            </dd>
          </div>
        )}

        <div>
          <dt className="label">STR and goAML gate</dt>
          <dd className="mt-1 text-ink-soft">{goamlDefense(alert)}</dd>
        </div>

        <div>
          <dt className="label">Audit replay</dt>
          <dd className="mt-1 font-mono text-[12px] text-ink-soft">{auditSummary(auditEntries)}</dd>
        </div>
      </dl>
    </section>
  )
}
