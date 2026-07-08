import type { AccessControlPosture } from '../types'

const roleTone: Record<string, string> = {
  analyst: 'border-line bg-paper text-ink-soft',
  qa: 'border-line bg-paper text-ink-soft',
  compliance: 'border-verified bg-verified-soft text-verified',
  modelRisk: 'border-line bg-paper text-ink-soft',
  amlOps: 'border-line bg-paper text-ink-soft',
  security: 'border-line bg-paper text-ink-soft',
  admin: 'border-flag bg-flag-soft text-flag',
}

export function AccessControlPostureCard({ posture }: { posture: AccessControlPosture | null }) {
  if (!posture) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Access control posture</h3>
        <p className="mt-3 text-[13px] text-ink-faint">Access-control contract has not loaded yet.</p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Access control posture</h3>
        <span className="rounded border border-line bg-paper px-2 py-1 text-[11px] font-medium text-ink-soft">
          {posture.mode}
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        Protected writes carry actor headers and are role-checked before state changes. The demo fallback is explicit:
        {' '}
        <span className="font-mono text-ink">{posture.demoFallbackActor.actorId}</span>
        {' '}
        ({posture.demoFallbackActor.actorRole}).
      </p>

      <div className="mt-4 overflow-hidden rounded-md border border-line">
        <table className="w-full border-collapse text-left">
          <thead className="bg-paper">
            <tr className="border-b border-line">
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Endpoint</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Roles</th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Control</th>
            </tr>
          </thead>
          <tbody>
            {posture.rules.map((rule) => (
              <tr key={`${rule.method}-${rule.endpoint}`} className="border-b border-line last:border-0">
                <td className="px-3 py-2.5">
                  <span className="font-mono text-[11px] text-ink">{rule.method} {rule.endpoint}</span>
                  <span className="mt-1 block text-[11px] text-ink-faint">audit: {rule.auditEvent}</span>
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {rule.allowedRoles.map((role) => (
                      <span key={role} className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${roleTone[role] ?? roleTone.analyst}`}>
                        {role}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-[12px] leading-relaxed text-ink-soft">{rule.control}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <h4 className="text-[12px] font-semibold text-ink">Four-eyes controls</h4>
          <ul className="mt-2 space-y-1.5">
            {posture.fourEyesControls.map((control) => (
              <li key={control} className="text-[12px] leading-relaxed text-ink-soft">{control}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-[12px] font-semibold text-ink">Non-claims</h4>
          <ul className="mt-2 space-y-1.5">
            {posture.nonClaims.map((claim) => (
              <li key={claim} className="text-[12px] leading-relaxed text-ink-faint">{claim}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
