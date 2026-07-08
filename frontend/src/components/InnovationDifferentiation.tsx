import type { InnovationDifferentiation as InnovationDifferentiationData } from '../types'

export function InnovationDifferentiation({ packet }: { packet: InnovationDifferentiationData | null }) {
  if (!packet) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Innovation differentiation</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Innovation differentiation unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Innovation differentiation</h3>
        <span className="rounded border border-verified bg-verified-soft px-2 py-1 text-[11px] font-medium text-verified">
          evidence-backed
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{packet.thesis}</p>

      <div className="mt-4 space-y-3">
        {packet.capabilities.map((capability) => (
          <article key={capability.name} className="rounded-md border border-line bg-paper p-3">
            <div className="text-[13px] font-semibold text-ink">{capability.name}</div>
            <dl className="mt-2 grid gap-2 text-[12px] leading-relaxed md:grid-cols-2">
              <div>
                <dt className="font-semibold text-ink-faint">Generic alternative</dt>
                <dd className="mt-1 text-ink-soft">{capability.genericAlternative}</dd>
              </div>
              <div>
                <dt className="font-semibold text-ink-faint">VerdictAML implementation</dt>
                <dd className="mt-1 text-ink-soft">{capability.verdictamlImplementation}</dd>
              </div>
            </dl>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Proof endpoints</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {capability.proofEndpoints.map((endpoint) => (
                    <span key={endpoint} className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink">
                      {endpoint}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Limit</div>
                <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{capability.limitation}</p>
              </div>
            </div>
            <p className="mt-3 border-t border-line pt-2 text-[12px] leading-relaxed text-ink-soft">
              {capability.defenseValue}
            </p>
          </article>
        ))}
      </div>

      <div className="mt-4 border-t border-line pt-3">
        <div className="label">Non-claims</div>
        <ul className="mt-2 space-y-1.5">
          {packet.nonClaims.map((claim) => (
            <li key={claim} className="flex gap-2 text-[12px] leading-relaxed text-ink-soft">
              <span aria-hidden className="shrink-0 font-mono text-flag">
                !
              </span>
              <span>{claim}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
