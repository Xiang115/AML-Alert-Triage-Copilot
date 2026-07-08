const gates = [
  {
    title: 'Historical replay',
    body: 'Run read-only on the bank\'s historical alerts. VerdictAML observes; the bank workflow remains unchanged.',
  },
  {
    title: 'Known-outcome comparison',
    body: 'Compare recommendations against analyst decisions, confirmed STRs, false-positive clears, and QA outcomes.',
  },
  {
    title: 'Threshold approval',
    body: 'Compliance signs off review, auto-clear, borderline, and QA-sample thresholds before automation acts.',
  },
  {
    title: 'Limited production auto-clear',
    body: 'Enable dismiss-only auto-clear for a bounded low-risk segment; escalations and filings stay human-gated.',
  },
  {
    title: 'Continuous monitoring',
    body: 'Track leakage, override rate, QA sample misses, drift, and typology coverage; rollback by threshold config.',
  },
]

export function ShadowModeValidation() {
  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Shadow-mode validation gate</h3>
        <span className="rounded border border-flag bg-flag-soft px-2 py-1 text-[11px] font-medium text-flag">
          production auto-clear locked
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        In a real bank deployment, auto-clear starts disabled. The system first proves its operating
        point against the bank&apos;s own historical alerts, then compliance approves the thresholds before
        any unattended dismissals affect production.
      </p>

      <ol className="mt-5 grid gap-2">
        {gates.map((gate, index) => (
          <li key={gate.title} className="rounded-md border border-line bg-paper px-3 py-2.5">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[11px] text-ink-faint">{String(index + 1).padStart(2, '0')}</span>
              <span className="text-[13px] font-semibold text-ink">{gate.title}</span>
            </div>
            <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{gate.body}</p>
          </li>
        ))}
      </ol>

      <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-faint">
        This is the production answer to false clears: do not beautify the metric; validate the threshold,
        keep QA sampling on, and make rollback a configuration change.
      </p>
    </section>
  )
}
