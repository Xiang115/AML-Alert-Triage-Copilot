import type { PilotAdoptionPlan as PilotAdoptionPlanData } from '../types'

function List({ items, marker = '+' }: { items: string[]; marker?: string }) {
  return (
    <ul className="mt-2 space-y-1.5">
      {items.map((item) => (
        <li key={item} className="flex gap-2 text-[12px] leading-relaxed text-ink-soft">
          <span aria-hidden className="shrink-0 font-mono text-verified">
            {marker}
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded border border-line bg-paper px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="mt-1 font-mono text-[16px] font-semibold tabular-nums text-ink">{value}</div>
      <div className="mt-0.5 text-[11px] leading-tight text-ink-faint">{sub}</div>
    </div>
  )
}

function SensitivityTable({ cases }: { cases: PilotAdoptionPlanData['sensitivityCases'] }) {
  return (
    <div className="mt-3 overflow-hidden rounded-md border border-line">
      <table className="w-full border-collapse text-left text-[12px]">
        <thead className="bg-paper text-[10px] uppercase tracking-wide text-ink-faint">
          <tr>
            <th className="px-3 py-2">Alerts/mo</th>
            <th className="px-3 py-2">Minutes saved</th>
            <th className="px-3 py-2">Hours returned</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((item) => (
            <tr key={`${item.monthlyAlerts}-${item.minutesSavedPerAlert}`} className="border-t border-line">
              <td className="px-3 py-2 font-mono tabular-nums text-ink">{item.monthlyAlerts.toLocaleString()}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-ink-soft">{item.minutesSavedPerAlert}m</td>
              <td className="px-3 py-2 font-mono tabular-nums text-ink">
                {item.estimatedMonthlyHoursReturned.toLocaleString()}h
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PilotAdoptionPlan({ plan }: { plan: PilotAdoptionPlanData | null }) {
  if (!plan) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Pilot adoption plan</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Pilot adoption plan unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Pilot adoption plan</h3>
        <span className="rounded border border-flag bg-flag-soft px-2 py-1 text-[11px] font-medium text-flag">
          conservative procurement
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        The adoption path is deliberately bank-realistic: read-only replay first, security and legal review,
        shadow pilot, then limited production only after compliance and model-risk sign-off.
      </p>

      <div className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <div className="label">Beachhead segment</div>
            <List items={plan.targetSegments} marker=">" />
          </div>
          <div>
            <div className="label">Buyer stakeholders</div>
            <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{plan.buyerStakeholders.join(' / ')}</p>
          </div>
        </div>
      </div>

      <section className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="label">Pilot economics</div>
            <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{plan.pilotEconomics.valueHypothesis}</p>
          </div>
          <span className="shrink-0 rounded border border-line bg-surface px-2 py-1 text-[11px] font-medium text-ink-soft">
            validation target
          </span>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <Metric
            label="Monthly alerts"
            value={plan.pilotEconomics.monthlyAlerts.toLocaleString()}
            sub="pilot assumption"
          />
          <Metric
            label="Current handling"
            value={`${plan.pilotEconomics.currentReviewMinutesPerAlert}m`}
            sub="per alert baseline"
          />
          <Metric
            label="Assisted handling"
            value={`${plan.pilotEconomics.assistedReviewMinutesPerAlert}m`}
            sub="per reviewed alert"
          />
          <Metric
            label="Hours saved"
            value={`${plan.pilotEconomics.estimatedMonthlyHoursSaved}h`}
            sub="estimated monthly"
          />
        </div>
        <p className="mt-2 text-[11px] leading-snug text-ink-faint">{plan.pilotEconomics.caveat}</p>
        <div className="mt-4 border-t border-line pt-3">
          <div className="label">Sensitivity cases</div>
          <SensitivityTable cases={plan.sensitivityCases} />
          <p className="mt-2 text-[11px] leading-snug text-ink-faint">{plan.sensitivityCases[0]?.caveat}</p>
        </div>
      </section>

      <section className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="label">Commercial model</div>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {plan.commercialModel.map((tier) => (
            <article key={tier.name} className="rounded border border-line bg-surface p-3">
              <div className="text-[13px] font-semibold text-ink">{tier.name}</div>
              <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{tier.customerStage}</p>
              <p className="mt-2 text-[12px] leading-relaxed text-ink">{tier.pricingModel}</p>
              <p className="mt-2 text-[11px] leading-snug text-ink-faint">{tier.conversionGate}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="label">Positioning</div>
        <List items={plan.competitivePositioning} marker=">" />
      </section>

      <section className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="label">8-week pilot timeline</div>
        <ol className="mt-2 space-y-2">
          {plan.pilotTimeline.map((step) => (
            <li key={step.week} className="grid gap-2 border-b border-line pb-2 last:border-0 last:pb-0 md:grid-cols-[90px_1fr]">
              <span className="font-mono text-[11px] text-ink-faint">{step.week}</span>
              <div>
                <p className="text-[12px] font-medium text-ink">{step.objective}</p>
                <p className="mt-1 text-[11px] leading-snug text-ink-faint">{step.owner} / {step.evidence}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <ol className="mt-4 space-y-2">
        {plan.phases.map((phase, index) => (
          <li key={phase.name} className="rounded-md border border-line bg-paper px-3 py-2.5">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[11px] text-ink-faint">{String(index + 1).padStart(2, '0')}</span>
              <span className="text-[13px] font-semibold text-ink">{phase.name}</span>
            </div>
            <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{phase.objective}</p>
            <div className="mt-2 grid gap-3 md:grid-cols-2">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Exit criteria</div>
                <List items={phase.exitCriteria} />
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Evidence produced</div>
                <List items={phase.evidenceProduced} />
              </div>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
        <div>
          <div className="label">Evidence basis</div>
          <List items={plan.validationEvidence} marker=">" />
        </div>
        <div>
          <div className="label">Success criteria</div>
          <List items={plan.successCriteria} />
        </div>
      </div>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
        <div>
          <div className="label">Procurement risks</div>
          <List items={plan.procurementRisks} marker="!" />
        </div>
        <div>
          <div className="label">Non-claims</div>
          <List items={plan.nonClaims} marker="!" />
        </div>
      </div>
    </section>
  )
}
