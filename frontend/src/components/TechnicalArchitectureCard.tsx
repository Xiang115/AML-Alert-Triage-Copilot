import type { ArchitectureComponent, TechnicalArchitecture } from '../types'

const layerTone: Record<ArchitectureComponent['layer'], string> = {
  bank: 'border-line bg-paper text-ink-soft',
  api: 'border-ink bg-paper text-ink',
  agent: 'border-verified bg-verified-soft text-verified',
  data: 'border-line bg-paper text-ink-soft',
  control: 'border-flag bg-flag-soft text-flag',
  ui: 'border-line-strong bg-surface text-ink',
}

function List({ title, items, marker = '+' }: { title: string; items: string[]; marker?: string }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase text-ink-faint">{title}</div>
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

export function TechnicalArchitectureCard({ architecture }: { architecture: TechnicalArchitecture | null }) {
  if (!architecture) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Technical architecture</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Technical architecture unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Technical architecture</h3>
        <span className="rounded border border-line bg-paper px-2 py-1 text-[11px] font-medium text-ink-soft">
          end-to-end flow
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{architecture.thesis}</p>

      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {architecture.components.map((component) => (
          <article key={component.id} className={`rounded-md border p-3 ${layerTone[component.layer]}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="text-[13px] font-semibold">{component.name}</div>
              <span className="shrink-0 rounded border border-current px-1.5 py-0.5 text-[10px] uppercase">
                {component.layer}
              </span>
            </div>
            <p className="mt-2 text-[12px] leading-relaxed">{component.responsibility}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {component.proofEndpoints.map((endpoint) => (
                <span key={endpoint} className="rounded border border-current px-1.5 py-0.5 font-mono text-[10px]">
                  {endpoint}
                </span>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="text-[11px] font-semibold uppercase text-ink-faint">Execution flow</div>
        <ol className="mt-2 space-y-2">
          {architecture.flows.map((flow, index) => (
            <li key={`${flow.source}-${flow.target}`} className="grid gap-2 border-b border-line pb-2 last:border-0 last:pb-0 md:grid-cols-[auto_1fr]">
              <span className="font-mono text-[11px] text-ink-faint">{String(index + 1).padStart(2, '0')}</span>
              <div>
                <div className="font-mono text-[12px] text-ink">{flow.source} -&gt; {flow.target}</div>
                <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{flow.payload}</p>
                <p className="mt-1 text-[12px] leading-relaxed text-flag">{flow.control}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
        <List title="Data handling" items={architecture.dataHandling} />
        <List title="AI execution" items={architecture.aiExecution} />
        <List title="Reliability controls" items={architecture.reliabilityControls} marker="!" />
        <List title="Demo path" items={architecture.demoPath} marker=">" />
      </div>

      <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-faint">{architecture.caveat}</p>
    </section>
  )
}
