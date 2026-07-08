import type { ReactNode } from 'react'
import type { AccessControlPosture, BankIntegrationContract, Governance as GovernanceData, GovernanceChangeRequestList, PilotAdoptionPlan as PilotAdoptionPlanData, QAOutcomeSummary, ReadinessSummary, TechnicalArchitecture, ValidationDossier } from '../types'
import { Badge } from './ui/Badge'
import { SuppressionFrontierCard } from './SuppressionFrontierCard'
import { BankIntegration } from './BankIntegration'
import { ShadowModeValidation } from './ShadowModeValidation'
import { OverrideFeedback } from './OverrideFeedback'
import { ValidationDossierCard } from './ValidationDossierCard'
import { ModelRiskChangeControl } from './ModelRiskChangeControl'
import { QAOutcomeSummaryCard } from './QAOutcomeSummaryCard'
import { AccessControlPostureCard } from './AccessControlPostureCard'
import { ArchitectureControlRoom } from './ArchitectureControlRoom'
import { TechnicalArchitectureCard } from './TechnicalArchitectureCard'
import { DefenseArtifacts } from './DefenseArtifacts'
import { PilotAdoptionPlan } from './PilotAdoptionPlan'

// Model governance (ADR-0020) — the "is this model-risk-managed?" surface (SR 11-7 / BNM). Every
// field is fact-supported: model + thresholds from config, "last validated" from a real held-out
// eval stamp, override rate from the audit trail. No fabricated numbers.

const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`)

function fmtDate(iso: string | null): string {
  if (!iso) return 'not yet validated'
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function Row({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-2 last:border-0">
      <dt className="text-[13px] text-ink-soft">{label}</dt>
      <dd className={`text-[13px] text-ink ${mono ? 'font-mono tabular-nums' : ''}`}>{value}</dd>
    </div>
  )
}

function Card({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="label">{title}</h3>
        {aside}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function Governance({
  data,
  validationDossier,
  integrationContract,
  accessControl,
  governanceChangeControl,
  qaOutcomes,
  technicalArchitecture,
  readinessSummary,
  pilotAdoptionPlan,
}: {
  data: GovernanceData | null
  validationDossier: ValidationDossier | null
  integrationContract: BankIntegrationContract | null
  accessControl: AccessControlPosture | null
  governanceChangeControl: GovernanceChangeRequestList | null
  qaOutcomes: QAOutcomeSummary | null
  technicalArchitecture: TechnicalArchitecture | null
  readinessSummary: ReadinessSummary | null
  pilotAdoptionPlan: PilotAdoptionPlanData | null
}) {
  return (
    <div className="h-full overflow-y-auto bg-paper p-8">
      <header className="mb-8">
        <h2 className="text-xl font-semibold tracking-tight text-ink">Model governance</h2>
        <p className="mt-1 max-w-2xl text-[13px] text-ink-soft">
          The model-risk view (SR 11-7 / BNM): what model runs, the operating-point thresholds, when it
          was last validated on held-out data, how the human overrides it, and the security posture — all
          fact-supported, none fabricated.
        </p>
      </header>

      {data ? (
        <div className="mx-auto max-w-6xl space-y-6">
          <ArchitectureControlRoom architecture={technicalArchitecture} readiness={readinessSummary} />

          <PilotAdoptionPlan plan={pilotAdoptionPlan} />

          <DefenseArtifacts readiness={readinessSummary} />

          <BankIntegration contract={integrationContract} />

          <ValidationDossierCard dossier={validationDossier} />

          <AccessControlPostureCard posture={accessControl} />

          {/* Override monitoring */}
          <OverrideFeedback override={data.override} />

          <ModelRiskChangeControl data={governanceChangeControl} />

          <QAOutcomeSummaryCard summary={qaOutcomes} />

          <ShadowModeValidation />

          <TechnicalArchitectureCard architecture={technicalArchitecture} />

          {/* Model */}
          <Card title="Model" aside={<Badge tone="bg-paper text-ink-soft">{data.model.provider}</Badge>}>
            <dl>
              <Row label="Workhorse (triage · STR drafting)" value={data.model.workhorse} />
              <Row label="Verifier (independent challenge)" value={data.model.verifier} />
              <Row label="Provider" value={data.model.provider} mono={false} />
            </dl>
          </Card>

          {/* Operating-point thresholds */}
          <Card title="Operating point — decision thresholds">
            <p className="mb-3 text-[13px] leading-relaxed text-ink-soft">
              The confidence boundaries that govern routing. Made explicit so the operating point is
              defensible, not hidden.
            </p>
            <dl>
              <Row label="Review threshold — below this, forced human review" value={pct(data.thresholds.review)} />
              <Row label="Auto-clear threshold — dismiss auto-cleared only at/above" value={pct(data.thresholds.autoClear)} />
              <Row label="Borderline margin — a dismiss within this of the review floor is flagged" value={`+${pct(data.thresholds.borderlineMargin)}`} />
              <Row label="QA sample rate — share of auto-cleared spot-checked" value={pct(data.thresholds.qaSample)} />
            </dl>
          </Card>

          {/* Closed-loop suppression frontier (ADR-0021) — the measured operating point of the
              self-learning auto-suppression. Only when the token-free eval has produced it. */}
          {data.suppressionFrontier && <SuppressionFrontierCard frontier={data.suppressionFrontier} />}

          {/* Last validation */}
          <Card
            title="Last held-out validation"
            aside={
              <Badge tone={data.validation.validatedAt ? 'bg-verified-soft text-verified' : 'bg-flag-soft text-flag'}>
                {data.validation.validatedAt ? 'Validated' : 'Pending'}
              </Badge>
            }
          >
            <dl>
              <Row label="Validated at" value={fmtDate(data.validation.validatedAt)} />
              <Row label="Model validated" value={data.validation.model ?? '—'} />
              <Row label="Held-out alerts (n)" value={data.validation.n?.toString() ?? '—'} />
              <Row label="Catch rate (recall)" value={pct(data.validation.recall)} />
              <Row label="Auto-clear leakage — P(cleared | true report)" value={pct(data.validation.autoClearLeakageRate)} />
              <Row label="Auto-clear precision" value={pct(data.validation.autoClearPrecision)} />
            </dl>
            <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
              Coverage: {data.validation.measuredTypologies.length} of{' '}
              {data.validation.measuredTypologies.length + data.validation.roadmapTypologies.length} curated cards
              measured ({data.validation.measuredTypologies.join(', ') || '—'}); roadmap:{' '}
              {data.validation.roadmapTypologies.join(', ') || '—'}.
            </p>
          </Card>

          {/* Security posture */}
          <Card title="Security & data-residency posture">
            <ul className="space-y-2">
              {data.securityPosture.map((line, i) => (
                <li key={i} className="flex gap-2 text-[13px] leading-relaxed text-ink-soft">
                  <span aria-hidden className="mt-px shrink-0 text-ink-faint">
                    {i === 0 ? '•' : '→'}
                  </span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      ) : (
        <div className="py-20 text-center text-[13px] text-ink-faint">Couldn't load governance data.</div>
      )}
    </div>
  )
}
