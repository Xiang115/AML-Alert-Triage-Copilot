import type { GovernanceOverride } from '../types'

function pct(v: number | null) {
  return v == null ? 'no decisions yet' : `${Math.round(v * 100)}%`
}

export function OverrideFeedback({ override }: { override: GovernanceOverride }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Override feedback loop</h3>
        <span className="rounded border border-line bg-paper px-2 py-1 font-mono text-[11px] text-ink-soft">
          {pct(override.overrideRate)}
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        Overrides are not treated as noise. They are the live calibration signal: every override keeps the
        AI call, human disposition, verifier status, confidence, and analyst reason together in audit.
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Step title="Capture" body="Override reason is recorded with the AI recommendation and final human disposition." />
        <Step title="Review" body="Compliance reviews override clusters by typology, threshold band, verifier status, and analyst reason." />
        <Step title="Update" body="Typology cards, thresholds, and QA sampling rules are changed deliberately; no hidden model training." />
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-px overflow-hidden rounded border border-line bg-line">
        <Stat label="Decisions" value={override.decisions.toString()} />
        <Stat label="Overrides" value={override.overrides.toString()} />
        <Stat label="Override rate" value={pct(override.overrideRate)} />
      </dl>
    </section>
  )
}

function Step({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-line bg-paper px-3 py-2.5">
      <div className="text-[13px] font-semibold text-ink">{title}</div>
      <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{body}</p>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface px-3 py-2.5">
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className="mt-0.5 font-mono text-[13px] font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  )
}
