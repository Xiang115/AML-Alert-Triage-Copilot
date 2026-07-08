import { useLearnedPatterns } from '../hooks/useLearnedPatterns'
import { useLearningLoopOpportunities } from '../hooks/useLearningLoopOpportunities'
import type { LearningLoopCandidate, LearningLoopOpportunities } from '../api'
import type { Alert } from '../types'

function formatClearedAt(clearedAt: string) {
  const parsed = new Date(clearedAt)
  return Number.isNaN(parsed.getTime()) ? clearedAt : parsed.toLocaleString()
}

function formatTypology(signature: string, typology: string | null) {
  if (typology) return typology

  const legacyMarker = '|typ:'
  const legacyIdx = signature.indexOf(legacyMarker)
  const marker = legacyMarker
  const idx = legacyIdx
  if (legacyIdx !== -1) return signature.slice(legacyIdx + legacyMarker.length)

  const currentMarker = 'typ='
  const currentIdx = signature.indexOf(currentMarker)
  if (currentIdx !== -1) {
    const end = signature.indexOf('|', currentIdx)
    return signature.slice(currentIdx + currentMarker.length, end === -1 ? undefined : end)
  }
  return idx === -1 ? '—' : signature.slice(idx + marker.length)
}

interface LearnedPatternsViewProps {
  alerts?: Alert[]
}

export function LearnedPatternsView({ alerts = [] }: LearnedPatternsViewProps) {
  const patterns = useLearnedPatterns()
  const opportunities = useLearningLoopOpportunities()
  const impactedBySignature = new Map<string, Alert[]>()

  for (const alert of alerts) {
    const suppression = alert.triage.suppression
    if (!suppression || suppression.status !== 'suppressed') continue
    const key = suppression.matchedPatternId || suppression.signature
    const current = impactedBySignature.get(key) ?? []
    current.push(alert)
    impactedBySignature.set(key, current)
  }

  return (
    <div className="h-full overflow-y-auto bg-paper p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Learning loop</h2>
          <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-ink-soft">
            Every learned suppression, the human decision it came from, and the future alerts it now
            removes from primary review.
          </p>
        </div>
        {patterns && (
          <div className="rounded border border-line bg-surface px-3 py-2 text-right">
            <div className="label">Active suppressions</div>
            <div className="mt-0.5 font-mono text-[18px] font-semibold tabular-nums text-ink">
              {patterns.length}
            </div>
          </div>
        )}
      </div>

      <SuppressionTrustStrip />
      <LearningOpportunityPanel opportunities={opportunities} />

      {patterns === null ? (
        <p className="mt-6 text-[13px] text-ink-faint">Loading learned patterns…</p>
      ) : patterns.length === 0 ? (
        <section className="mt-6 rounded-lg border border-line bg-surface p-6">
          <h3 className="text-[14px] font-semibold text-ink">No learning paths yet</h3>
          <p className="mt-1.5 max-w-xl text-[13px] leading-relaxed text-ink-soft">
            Dismiss a benign alert and its pattern will appear here with the future alerts it affects.
          </p>
        </section>
      ) : (
        <div className="mt-6 space-y-3">
          {patterns.map((pattern) => (
            <LearningPathCard
              key={pattern.signature}
              pattern={pattern}
              impactedAlerts={impactedBySignature.get(pattern.signature) ?? []}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function LearningOpportunityPanel({
  opportunities,
}: {
  opportunities: LearningLoopOpportunities | null
}) {
  const candidates = opportunities?.candidates ?? []

  return (
    <section className="mt-5 rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="label">Full-population learning scan</h3>
          <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-ink-soft">
            Every copilot-run alert is scanned as a possible human-taught source. Reusable sources show
            future look-alikes removed from primary review; blocked matches show the safety gate that
            stopped suppression.
          </p>
        </div>
        <span className="shrink-0 rounded border border-line bg-paper px-2 py-1 font-mono text-[11px] text-ink-soft">
          replayable evidence
        </span>
      </div>

      {opportunities === null ? (
        <p className="mt-4 text-[12px] text-ink-faint">Loading learning scan…</p>
      ) : (
        <>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <OpportunityMetric label="Alerts scanned" value={String(opportunities.scannedAlerts)} />
            <OpportunityMetric label="Teachable dismissals" value={String(opportunities.teachableSources)} />
            <OpportunityMetric label="Reusable sources" value={String(opportunities.reusableSources)} />
            <OpportunityMetric label="Future look-alikes removed" value={String(opportunities.affectedFutureAlerts)} />
          </div>

          <div className="mt-4 rounded-md border border-line bg-paper">
            <div className="grid grid-cols-[auto_1fr_auto] gap-3 border-b border-line px-3 py-2">
              <span className="label">Source candidate</span>
              <span className="label">Measured effect</span>
              <span className="label text-right">Gate</span>
            </div>
            <div className="max-h-[440px] divide-y divide-line overflow-y-auto">
              {candidates.map((candidate) => (
                <LearningCandidateRow key={candidate.sourceAlertId} candidate={candidate} />
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  )
}

function OpportunityMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-paper px-3 py-2">
      <div className="label">{label}</div>
      <div className="mt-1 font-mono text-[18px] font-semibold tabular-nums text-ink">{value}</div>
    </div>
  )
}

function LearningCandidateRow({ candidate }: { candidate: LearningLoopCandidate }) {
  const status =
    candidate.affectedFutureAlerts.length > 0 ? 'reusable' : candidate.canTeach ? 'teaches only source' : 'blocked'
  const statusClass =
    candidate.affectedFutureAlerts.length > 0
      ? 'border-verified/30 bg-verified/10 text-verified'
      : candidate.canTeach
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-700'
        : 'border-line bg-surface text-ink-faint'

  return (
    <div className="grid grid-cols-[auto_1fr_auto] gap-3 px-3 py-2 text-[12px]">
      <div className="min-w-[128px]">
        <a className="font-mono text-ink underline underline-offset-2" href={`#/alerts/${candidate.sourceAlertId}`}>
          {candidate.sourceAlertId}
        </a>
        <div className="mt-0.5 max-w-[180px] truncate text-ink-faint">{candidate.holderName}</div>
        <div className="mt-1 font-mono text-[10px] text-ink-faint">{candidate.typology ?? 'NONE'}</div>
      </div>

      <div className="min-w-0">
        {candidate.affectedFutureAlerts.length > 0 ? (
          <div>
            <div className="font-semibold text-verified">
              {candidate.affectedFutureAlerts.length} future look-alike
              {candidate.affectedFutureAlerts.length === 1 ? '' : 's'} removed from primary review
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {candidate.affectedFutureAlerts.map((alert) => (
                <a
                  key={alert.alertId}
                  href={`#/alerts/${alert.alertId}`}
                  className="rounded border border-line bg-surface px-2 py-1 font-mono text-[11px] text-ink hover:bg-paper"
                  title={`${alert.holderName} · ${alert.recommendation} · ${(alert.confidence * 100).toFixed(0)}%`}
                >
                  {alert.alertId}
                </a>
              ))}
            </div>
          </div>
        ) : candidate.canTeach ? (
          <div>
            <div className="font-semibold text-ink">Teachable, but no current future-work reduction.</div>
            <div className="mt-1 text-ink-faint">
              {candidate.blockedFutureAlerts[0]?.reason ??
                'No future alert in the loaded population shares a reusable, eligible signature.'}
            </div>
          </div>
        ) : (
          <div>
            <div className="font-semibold text-ink">No learning effect.</div>
            <div className="mt-1 text-ink-faint">{candidate.blockedReason ?? 'Suppression gate did not pass.'}</div>
          </div>
        )}
        {candidate.signature && <div className="mt-1 truncate font-mono text-[10px] text-ink-faint">{candidate.signature}</div>}
      </div>

      <div className="text-right">
        <span className={`inline-flex rounded border px-2 py-1 font-mono text-[10px] ${statusClass}`}>
          {status}
        </span>
        <div className="mt-1 font-mono text-[10px] text-ink-faint">
          {candidate.recommendation}/{candidate.verifierStatus}
        </div>
      </div>
    </div>
  )
}

function LearningPathCard({
  pattern,
  impactedAlerts,
}: {
  pattern: {
    signature: string
    typology: string | null
    sourceAlertId: string
    clearedCount: number
    clearedAt: string
  }
  impactedAlerts: Alert[]
}) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-[14px] font-semibold text-ink">Learning path</h3>
          <div className="mt-1 font-mono text-[12px] text-ink-soft">{pattern.signature}</div>
        </div>
        <div className="text-right">
          <div className="label">Future alerts affected</div>
          <div className="font-mono text-[18px] font-semibold tabular-nums text-verified">
            {impactedAlerts.length}
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-4">
        <PathMetric label="Typology" value={formatTypology(pattern.signature, pattern.typology)} />
        <PathMetric label="Learned from" value={pattern.sourceAlertId} href={`#/alerts/${pattern.sourceAlertId}`} />
        <PathMetric label="Times cleared" value={String(pattern.clearedCount)} />
        <PathMetric label="Latest clearance" value={formatClearedAt(pattern.clearedAt)} />
      </div>

      <div className="mt-3 rounded-md border border-line bg-paper">
        <div className="border-b border-line px-3 py-2">
          <h4 className="label">Future look-alikes removed from primary review</h4>
        </div>
        {impactedAlerts.length === 0 ? (
          <p className="px-3 py-3 text-[12px] text-ink-faint">
            No currently loaded alert is being routed by this suppression.
          </p>
        ) : (
          <div className="divide-y divide-line">
            {impactedAlerts.map((alert) => (
              <a
                key={alert.alertId}
                href={`#/alerts/${alert.alertId}`}
                className="grid grid-cols-[auto_1fr_auto] gap-3 px-3 py-2 text-[12px] hover:bg-surface"
              >
                <span className="font-mono text-ink">{alert.alertId}</span>
                <span className="truncate text-ink-soft">{alert.account.holderName}</span>
                <span className="label text-verified">{alert.routing ?? 'needsReview'}</span>
              </a>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function PathMetric({ label, value, href }: { label: string; value: string; href?: string }) {
  return (
    <div className="rounded border border-line bg-paper px-3 py-2">
      <div className="label">{label}</div>
      {href ? (
        <a className="mt-1 block truncate font-mono text-[12px] text-ink underline underline-offset-2" href={href}>
          {value}
        </a>
      ) : (
        <div className="mt-1 truncate text-[12px] text-ink-soft">{value}</div>
      )}
    </div>
  )
}

function SuppressionTrustStrip() {
  const controls = [
    {
      title: 'Learns only from human dismissals',
      body: 'A pattern cites the analyst decision that cleared it; escalations never teach suppression.',
    },
    {
      title: 'Acts only inside the firewall',
      body: 'It can only clear a dismiss with verifier agreement, confidence above the review floor, and a benign ledger envelope.',
    },
    {
      title: 'Cannot file or escalate',
      body: 'Suppression only removes review work for bounded benign look-alikes; STR filing remains human-owned.',
    },
    {
      title: 'Revoked by network risk',
      body: 'If the counterparty becomes a mule-network consolidation hub, the clearance is cancelled and routed to review.',
    },
  ]

  return (
    <section className="mt-5 rounded-lg border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="label">Suppression firewall</h3>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">
            Reusable analyst judgment is allowed to shrink the queue, but not to bypass AML controls.
          </p>
        </div>
        <span className="shrink-0 rounded border border-line bg-paper px-2 py-1 font-mono text-[11px] text-ink-soft">
          dismiss-only
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {controls.map((control) => (
          <div key={control.title} className="rounded border border-line bg-paper px-3 py-2">
            <div className="text-[12px] font-semibold text-ink">{control.title}</div>
            <p className="mt-1 text-[11px] leading-snug text-ink-faint">{control.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
