import type { ReadinessSummary } from '../types'

const artifacts = [
  {
    name: 'Finals evidence bundle',
    endpoint: '/finals/evidence-bundle',
    proves: 'Single packet tying the finals claims to live contracts and readiness state.',
  },
  {
    name: 'Metrics',
    endpoint: '/metrics',
    proves: 'Held-out performance, baseline comparison, and modest-metrics honesty.',
  },
  {
    name: 'Queue briefing',
    endpoint: '/queue/briefing',
    proves: 'The Queue Agent produces a real worklist, blocked reasons, and next actions.',
  },
  {
    name: 'Operational impact',
    endpoint: '/operations/impact',
    proves: 'Workflow pain and measurable shift-level workload reduction.',
  },
  {
    name: 'Technical architecture',
    endpoint: '/architecture/technical',
    proves: 'End-to-end system shape, data flow, AI execution, and controls.',
  },
  {
    name: 'Validation dossier',
    endpoint: '/governance/validation-dossier',
    proves: 'Auto-clear leakage, shadow-only state, release gates, and prohibited actions.',
  },
  {
    name: 'Integration contract',
    endpoint: '/integration/contract',
    proves: 'Required bank fields, outbound artifacts, production gates, and non-goals.',
  },
  {
    name: 'Pilot adoption plan',
    endpoint: '/pilot/adoption-plan',
    proves: 'Commercial rollout path, buyer stakeholders, pilot economics, and risks.',
  },
  {
    name: 'Innovation differentiation',
    endpoint: '/innovation/differentiation',
    proves: 'Why this is not just a chatbot: agents, workflow automation, controls, and limits.',
  },
  {
    name: 'Finals Q&A defense',
    endpoint: '/finals/qna-defense',
    proves: 'Likely judge objections mapped to answers, evidence endpoints, and traps to avoid.',
  },
]

function statusTone(readiness: ReadinessSummary | null) {
  if (!readiness) return 'border-line bg-paper text-ink-soft'
  return readiness.status === 'pass'
    ? 'border-verified bg-verified-soft text-verified'
    : 'border-flag bg-flag-soft text-flag'
}

export function DefenseArtifacts({ readiness }: { readiness: ReadinessSummary | null }) {
  const checksByEndpoint = new Map((readiness?.checks ?? []).map((check) => [check.endpoint, check]))
  const rows = artifacts.map((artifact) => ({
    ...artifact,
    check: checksByEndpoint.get(artifact.endpoint) ?? null,
  }))
  const ready = readiness?.status === 'pass'

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Defense artifacts</h3>
        <span className={`rounded border px-2 py-1 text-[11px] font-medium ${statusTone(readiness)}`}>
          {readiness ? (ready ? 'readiness passed' : 'readiness failed') : 'readiness pending'}
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        The essential machine-readable contracts behind the finals claims. Per-alert proof stays inside
        the selected alert detail; this table stays focused on system, market, validation, and architecture evidence.
      </p>

      <div className="mt-4 overflow-hidden rounded-md border border-line">
        <table className="w-full border-collapse text-left">
          <thead className="bg-paper">
            <tr className="border-b border-line">
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Artifact</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Endpoint</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Defense value</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((artifact) => (
              <tr key={artifact.endpoint} className="border-b border-line last:border-0">
                <td className="px-3 py-2.5 text-[12px] font-semibold text-ink">{artifact.name}</td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-ink">{artifact.endpoint}</td>
                <td className="px-3 py-2.5 text-[12px] leading-relaxed text-ink-soft">{artifact.proves}</td>
                <td className="px-3 py-2.5 text-[12px] leading-relaxed">
                  <span className={
                    artifact.check
                      ? artifact.check.ok ? 'font-medium text-verified' : 'font-medium text-flag'
                      : 'font-medium text-ink-faint'
                  }>
                    {artifact.check ? (artifact.check.ok ? 'pass' : 'fail') : 'not tracked'}
                  </span>
                  {artifact.check && artifact.check.detail !== 'ok' && (
                    <span className="ml-2 text-ink-faint">{artifact.check.detail}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
        {readiness
          ? `Backend readiness checked ${readiness.checks.length} contract(s) at ${readiness.checkedAt}.`
          : 'Backend readiness summary has not loaded yet.'}
      </p>
    </section>
  )
}
