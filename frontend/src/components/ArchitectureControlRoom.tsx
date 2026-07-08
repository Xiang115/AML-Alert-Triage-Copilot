import type { ArchitectureComponent, ReadinessSummary, TechnicalArchitecture } from '../types'

const laneOrder: ArchitectureComponent['layer'][] = ['bank', 'api', 'agent', 'control', 'ui']

const laneLabel: Record<ArchitectureComponent['layer'], string> = {
  bank: 'Bank systems',
  api: 'API + store',
  agent: 'AI workbench',
  control: 'Control plane',
  data: 'Data layer',
  ui: 'Reviewer console',
}

const laneTone: Record<ArchitectureComponent['layer'], string> = {
  bank: 'border-line bg-paper text-ink-soft',
  api: 'border-line-strong bg-surface text-ink',
  agent: 'border-verified bg-verified-soft text-verified',
  control: 'border-flag bg-flag-soft text-flag',
  data: 'border-line bg-paper text-ink-soft',
  ui: 'border-line-strong bg-surface text-ink',
}

const systemProofEndpoints = [
  {
    endpoint: '/architecture/technical',
    label: 'Architecture',
    value: 'Typed component and flow contract.',
  },
  {
    endpoint: '/integration/contract',
    label: 'Integration',
    value: 'Bank-system seams and required fields.',
  },
  {
    endpoint: '/queue/briefing',
    label: 'Queue agent',
    value: 'Operational worklist and blocked reasons.',
  },
  {
    endpoint: '/operations/impact',
    label: 'Impact',
    value: 'Workload and control caveats.',
  },
  {
    endpoint: '/governance/validation-dossier',
    label: 'Validation',
    value: 'Leakage, gates, prohibited actions.',
  },
  {
    endpoint: '/finals/evidence-bundle',
    label: 'Evidence',
    value: 'Single judge-facing evidence packet.',
  },
]

function endpointStatus(readiness: ReadinessSummary | null, endpoint: string) {
  return readiness?.checks.find((check) => check.endpoint === endpoint) ?? null
}

function componentsForLane(architecture: TechnicalArchitecture, layer: ArchitectureComponent['layer']) {
  return architecture.components.filter((component) => component.layer === layer)
}

export function ArchitectureControlRoom({
  architecture,
  readiness,
}: {
  architecture: TechnicalArchitecture | null
  readiness: ReadinessSummary | null
}) {
  if (!architecture) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Architecture control room</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Architecture contract unavailable.</div>
      </section>
    )
  }

  const passedEndpoints = systemProofEndpoints.filter((proof) => endpointStatus(readiness, proof.endpoint)?.ok).length
  const controlFlows = architecture.flows.filter((flow) => flow.control)

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="label">Architecture control room</h3>
          <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-ink-soft">
            {architecture.thesis}
          </p>
        </div>
        <div className="rounded-md border border-line bg-paper px-3 py-2 text-right">
          <div className="font-mono text-[18px] font-semibold tabular-nums text-ink">
            {passedEndpoints}/{systemProofEndpoints.length}
          </div>
          <div className="text-[11px] font-medium uppercase text-ink-faint">essential contracts passing</div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-5">
        {laneOrder.map((layer) => {
          const components = componentsForLane(architecture, layer)
          return (
            <article key={layer} className={`min-h-36 rounded-md border p-3 ${laneTone[layer]}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="text-[11px] font-semibold uppercase">{laneLabel[layer]}</div>
                <div className="font-mono text-[11px] tabular-nums">{components.length}</div>
              </div>
              <div className="mt-3 space-y-2">
                {components.length ? (
                  components.map((component) => (
                    <div key={component.id} className="rounded border border-current bg-white/40 px-2 py-1.5">
                      <div className="text-[12px] font-semibold leading-snug">{component.name}</div>
                      <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed opacity-80">
                        {component.responsibility}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-[12px] leading-relaxed opacity-70">No component registered.</div>
                )}
              </div>
            </article>
          )
        })}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-md border border-line bg-paper p-3">
          <div className="text-[11px] font-semibold uppercase text-ink-faint">Control path</div>
          <ol className="mt-3 space-y-2">
            {architecture.flows.map((flow, index) => (
              <li key={`${flow.source}-${flow.target}`} className="grid grid-cols-[2.5rem_1fr] gap-3 border-b border-line pb-2 last:border-0 last:pb-0">
                <span className="font-mono text-[11px] text-ink-faint">{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <div className="font-mono text-[12px] text-ink">
                    {flow.source} -&gt; {flow.target}
                  </div>
                  <div className="mt-1 text-[12px] leading-relaxed text-ink-soft">{flow.payload}</div>
                  <div className="mt-1 text-[12px] leading-relaxed text-flag">{flow.control}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="space-y-4">
          <div className="rounded-md border border-line bg-paper p-3">
            <div className="text-[11px] font-semibold uppercase text-ink-faint">Autonomy gates</div>
            <ul className="mt-3 space-y-2">
              {controlFlows.slice(0, 5).map((flow) => (
                <li key={`${flow.source}-${flow.target}-gate`} className="text-[12px] leading-relaxed text-ink-soft">
                  <span className="font-mono text-flag">{flow.target}</span>: {flow.control}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-md border border-line bg-paper p-3">
            <div className="text-[11px] font-semibold uppercase text-ink-faint">Essential proof surface</div>
            <div className="mt-3 grid gap-2">
              {systemProofEndpoints.map((proof) => {
                const check = endpointStatus(readiness, proof.endpoint)
                const status = check ? (check.ok ? 'pass' : 'fail') : 'not checked'
                const tone = check?.ok
                  ? 'border-verified bg-verified-soft text-verified'
                  : check
                    ? 'border-flag bg-flag-soft text-flag'
                    : 'border-line bg-surface text-ink-soft'
                return (
                  <div key={proof.endpoint} className={`rounded border px-2.5 py-2 ${tone}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-[12px] font-semibold">{proof.label}</div>
                        <div className="mt-0.5 text-[11px] leading-relaxed opacity-80">{proof.value}</div>
                        <div className="mt-1 font-mono text-[10px]">{proof.endpoint}</div>
                      </div>
                      <span className="shrink-0 font-mono text-[10px] uppercase">{status}</span>
                    </div>
                  </div>
                )
              })}
            </div>
            <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
              {readiness
                ? `Readiness checked ${readiness.checks.length} backend contract(s) at ${readiness.checkedAt}.`
                : 'Readiness has not loaded yet.'}
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
