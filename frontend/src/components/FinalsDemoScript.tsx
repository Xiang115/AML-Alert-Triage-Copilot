import type { FinalsDemoScript as FinalsDemoScriptData } from '../types'

function List({ title, items, marker = '+' }: { title: string; items: string[]; marker?: string }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase text-ink-faint">{title}</div>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-[12px] leading-relaxed text-ink-soft">
            <span aria-hidden className="shrink-0 font-mono text-flag">{marker}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function FinalsDemoScript({ script }: { script: FinalsDemoScriptData | null }) {
  if (!script) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Finals demo path</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Finals demo path unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Finals demo path</h3>
        <span className="rounded border border-line bg-paper px-2 py-1 text-[11px] font-medium text-ink-soft">
          {script.totalMinutes} min run
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{script.openingLine}</p>

      <ol className="mt-4 space-y-2">
        {script.steps.map((step, index) => (
          <li key={step.title} className="rounded-md border border-line bg-paper p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-[11px] text-ink-faint">{String(index + 1).padStart(2, '0')}</span>
                  <span className="text-[13px] font-semibold text-ink">{step.title}</span>
                </div>
                <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{step.objective}</p>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-ink-faint">{step.timeboxMinutes}m</span>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <div className="text-[11px] font-semibold uppercase text-ink-faint">Action</div>
                <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{step.action}</p>
                <div className="mt-2 font-mono text-[11px] text-ink-faint">{step.route}</div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase text-ink-faint">Evidence</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {step.evidenceEndpoints.map((endpoint) => (
                    <span key={endpoint} className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink">
                      {endpoint}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-[12px] leading-relaxed text-verified">{step.judgeTakeaway}</p>
              </div>
            </div>
            <p className="mt-3 border-t border-line pt-2 text-[12px] leading-relaxed text-flag">{step.fallback}</p>
          </li>
        ))}
      </ol>

      <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
        <List title="Fallback moves" items={script.fallbackMoves} marker="!" />
        <List title="Do not claim" items={script.nonClaims} marker="!" />
      </div>

      <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-soft">{script.closingLine}</p>
    </section>
  )
}
