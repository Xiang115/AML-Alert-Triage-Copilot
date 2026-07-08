import type { BankIntegrationContract, IntegrationDataField } from '../types'

function FieldList({ fields }: { fields: IntegrationDataField[] }) {
  return (
    <ul className="mt-2 space-y-2">
      {fields.map((field) => (
        <li key={field.name} className="rounded-md border border-line bg-paper px-3 py-2">
          <div className="text-[12px] font-semibold text-ink">{field.name}</div>
          <div className="mt-0.5 text-[11px] text-ink-faint">{field.source}</div>
          <p className="mt-1 text-[12px] leading-snug text-ink-soft">{field.reason}</p>
        </li>
      ))}
    </ul>
  )
}

function SimpleList({ items, marker }: { items: string[]; marker: string }) {
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

export function BankIntegration({ contract }: { contract: BankIntegrationContract | null }) {
  if (!contract) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Bank integration path</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Integration contract unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Bank integration path</h3>
        <span className="rounded border border-line bg-paper px-2 py-1 text-[11px] font-medium text-ink-soft">
          {contract.mode === 'shadowFirst' ? 'shadow mode first' : contract.mode}
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        VerdictAML sits between the bank&apos;s existing transaction-monitoring system and the analyst&apos;s
        case-management flow. It does not replace the source detector; it makes each alert defensible
        before a human decision or goAML filing.
      </p>

      <div className="mt-3 text-[12px] text-ink-faint">
        Inbound systems: {contract.inboundSystems.join(' / ')}
      </div>

      <ol className="mt-5 space-y-2">
        {contract.workflow.map((step, index) => (
          <li key={step.title} className="grid grid-cols-[1.75rem_1fr] gap-2">
            <div className="flex flex-col items-center">
              <span className="flex h-6 w-6 items-center justify-center rounded border border-line bg-paper font-mono text-[11px] text-ink">
                {index + 1}
              </span>
              {index < contract.workflow.length - 1 && <span className="mt-1 h-full min-h-4 w-px bg-line" />}
            </div>
            <div className="pb-2">
              <div className="text-[13px] font-semibold text-ink">{step.title}</div>
              <div className="mt-0.5 text-[12px] leading-relaxed text-ink-soft">{step.body}</div>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
        <div>
          <div className="label">Minimum data access</div>
          <FieldList fields={contract.minimumRequiredFields} />
        </div>
        <div>
          <div className="label">Optional enrichments</div>
          <FieldList fields={contract.optionalEnrichments} />
        </div>
      </div>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-3">
        <div>
          <div className="label">Outbound artifacts</div>
          <SimpleList items={contract.outboundArtifacts} marker="+" />
        </div>
        <div>
          <div className="label">Production gates</div>
          <SimpleList items={contract.productionGates} marker="+" />
        </div>
        <div>
          <div className="label">Non-goals</div>
          <SimpleList items={contract.nonGoals} marker="!" />
        </div>
      </div>
    </section>
  )
}
