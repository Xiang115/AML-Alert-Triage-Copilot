import type { QAOutcomeSummary } from '../types'

const pct = (value: number | null | undefined) => (value == null ? 'not measured' : `${Math.round(value * 100)}%`)

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function QAOutcomeSummaryCard({ summary }: { summary: QAOutcomeSummary | null }) {
  if (!summary) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">QA outcome loop</h3>
        <p className="mt-3 text-[13px] text-ink-faint">QA outcome summary has not loaded yet.</p>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">QA outcome loop</h3>
        <span className="rounded border border-line bg-paper px-2 py-1 text-[11px] font-medium text-ink-soft">
          {summary.reviewed} reviewed
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        Auto-cleared and manually sampled alerts can be confirmed or marked as missed suspicion. Misses stay visible and feed threshold review instead of silently tuning the model.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-md border border-line bg-paper p-3">
          <p className="text-[11px] uppercase tracking-wide text-ink-faint">Confirmed clears</p>
          <p className="mt-1 font-mono text-lg font-semibold text-verified">{summary.confirmedClears}</p>
        </div>
        <div className="rounded-md border border-line bg-paper p-3">
          <p className="text-[11px] uppercase tracking-wide text-ink-faint">Missed suspicion</p>
          <p className="mt-1 font-mono text-lg font-semibold text-flag">{summary.missedSuspicion}</p>
        </div>
        <div className="rounded-md border border-line bg-paper p-3">
          <p className="text-[11px] uppercase tracking-wide text-ink-faint">QA miss rate</p>
          <p className="mt-1 font-mono text-lg font-semibold text-ink">{pct(summary.missRate)}</p>
        </div>
      </div>

      {summary.outcomes.length ? (
        <div className="mt-4 overflow-hidden rounded-md border border-line">
          <table className="w-full border-collapse text-left">
            <thead className="bg-paper">
              <tr className="border-b border-line">
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Alert</th>
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Outcome</th>
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Reviewer</th>
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Note</th>
              </tr>
            </thead>
            <tbody>
              {summary.outcomes.map((outcome) => (
                <tr key={`${outcome.alertId}-${outcome.reviewedAt}`} className="border-b border-line last:border-0">
                  <td className="px-3 py-2.5 font-mono text-[11px] text-ink">{outcome.alertId}</td>
                  <td className="px-3 py-2.5 text-[12px] font-medium text-ink">{outcome.outcome}</td>
                  <td className="px-3 py-2.5 text-[12px] text-ink-soft">
                    {outcome.reviewer}
                    <span className="block text-[11px] text-ink-faint">{fmtDate(outcome.reviewedAt)}</span>
                  </td>
                  <td className="px-3 py-2.5 text-[12px] leading-relaxed text-ink-soft">{outcome.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 rounded-md border border-line bg-paper px-3 py-2 text-[12px] leading-relaxed text-ink-faint">
          No QA outcomes recorded in this session yet. The endpoint is live so sampled clears can be reviewed without changing model thresholds.
        </p>
      )}
    </section>
  )
}
