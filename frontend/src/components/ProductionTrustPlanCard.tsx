import type { ProductionTrustPlan } from '../types'

function List({ title, items, marker = '+' }: { title: string; items: string[]; marker?: string }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{title}</div>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-[12px] leading-relaxed text-ink-soft">
            <span aria-hidden className="shrink-0 font-mono text-verified">{marker}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-line bg-paper px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="mt-1 font-mono text-[18px] font-semibold tabular-nums text-ink">{value}</div>
    </div>
  )
}

const areaLabel: Record<ProductionTrustPlan['items'][number]['area'], string> = {
  integration: 'Integration',
  dataAccess: 'Data access',
  falsePositiveGovernance: 'False-positive governance',
  validation: 'Validation',
  productionGate: 'Production gate',
}

export function ProductionTrustPlanCard({ plan }: { plan: ProductionTrustPlan | null }) {
  if (!plan) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Production trust plan</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Production trust plan unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Production trust plan</h3>
        <span className="rounded border border-flag bg-flag-soft px-2 py-1 text-[11px] font-medium text-flag">
          bank-trust gates
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{plan.position}</p>

      <div className="mt-4 grid gap-2 md:grid-cols-4">
        <Metric label="Target systems" value={plan.targetSystems.length} />
        <Metric label="Data access" value={plan.minimumDataAccess.length} />
        <Metric label="Controls" value={plan.governanceControls.length} />
        <Metric label="Validation gates" value={plan.validationGates.length} />
      </div>

      <div className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="label">Judge response</div>
        <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{plan.judgeResponse}</p>
      </div>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
        <List title="Real bank systems" items={plan.targetSystems} />
        <List title="Minimum data access" items={plan.minimumDataAccess} />
        <List title="False-positive governance" items={plan.governanceControls} marker="!" />
        <List title="Validation gates" items={plan.validationGates} marker=">" />
      </div>

      <ol className="mt-4 space-y-2 border-t border-line pt-4">
        {plan.items.map((item, index) => (
          <li key={item.area} className="rounded-md border border-line bg-paper px-3 py-2.5">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[11px] text-ink-faint">{String(index + 1).padStart(2, '0')}</span>
              <span className="text-[13px] font-semibold text-ink">{areaLabel[item.area]}</span>
            </div>
            <p className="mt-1 text-[12px] leading-relaxed text-ink">{item.requirement}</p>
            <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{item.implementation}</p>
            <p className="mt-1 text-[12px] leading-relaxed text-flag">{item.productionGate}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {item.evidenceEndpoints.map((endpoint) => (
                <span key={endpoint} className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[10px] text-ink-soft">
                  {endpoint}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-4 border-t border-line pt-4">
        <List title="Non-claims" items={plan.nonClaims} marker="!" />
      </div>
    </section>
  )
}
