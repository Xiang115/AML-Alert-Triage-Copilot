import type { SuppressionFrontier, SuppressionPoint } from '../types'
import { Badge } from './ui/Badge'

// Closed-loop suppression frontier (ADR-0021): the measured leakage/coverage trade-off of the
// self-learning auto-suppression. A single series (the achievable frontier) — title names it, so no
// legend; the two decisions on it (the naive strawman, the pre-registered operating point) are
// status-coloured AND direct-labelled, never colour alone. Inline SVG (no chart lib); tokens only.

const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`
const pct0 = (v: number) => `${Math.round(v * 100)}%`

// Plot geometry (viewBox units).
const W = 480, H = 236, PAD_L = 46, PAD_R = 14, PAD_T = 14, PAD_B = 30
const X_MAX = 0.5 // coverage domain
const Y_MAX = 0.16 // leakage domain
const sx = (c: number) => PAD_L + (Math.min(c, X_MAX) / X_MAX) * (W - PAD_L - PAD_R)
const sy = (l: number) => PAD_T + (1 - Math.min(l, Y_MAX) / Y_MAX) * (H - PAD_T - PAD_B)

const Y_TICKS = [0, 0.04, 0.08, 0.12, 0.16]
const X_TICKS = [0, 0.1, 0.2, 0.3, 0.4, 0.5]

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="rounded-md border border-line bg-paper px-3 py-2">
      <div className="label text-[10px]">{label}</div>
      <div className={`mt-0.5 font-mono text-lg tabular-nums ${tone ?? 'text-ink'}`}>{value}</div>
      {sub && <div className="text-[11px] text-ink-faint tabular-nums">{sub}</div>}
    </div>
  )
}

export function SuppressionFrontierCard({ frontier }: { frontier: SuppressionFrontier }) {
  const { naive, operatingPoint: op, curve } = frontier
  const line = curve.map((p: SuppressionPoint) => `${sx(p.coverage).toFixed(1)},${sy(p.leakage).toFixed(1)}`).join(' ')

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="label">Closed-loop suppression — leakage vs coverage</h3>
        <Badge tone="bg-verified-soft text-verified">Measured · token-free</Badge>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
        The self-learning auto-suppression trades <span className="text-ink">coverage</span> (queue it clears)
        against <span className="text-ink">leakage</span> (true laundering it wrongly clears). Held-out,
        label-blind, leave-one-out — {frontier.n} alerts ({frontier.nBenign} benign).
      </p>

      {/* Key numbers double as the text alternative to the plot. */}
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Tile label="Naive envelope" value={pct1(naive.leakage)} sub={`${naive.leaked}/${naive.suppressed} leaked`} tone="text-escalate" />
        <Tile label="Operating point" value={pct1(op.leakage)} sub={`${op.leaked}/${op.suppressed} leaked`} tone="text-verified" />
        <Tile label="Coverage @ op" value={pct0(op.coverage)} sub="of the queue" />
        <Tile label="95% upper bound" value={op.leakage95Upper != null ? pct1(op.leakage95Upper) : '—'} sub="at this N" />
      </div>

      <figure className="mt-4">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
          aria-label={`Leakage vs coverage frontier: naive envelope leaks ${pct1(naive.leakage)} at ${pct0(naive.coverage)} coverage; the pre-registered operating point leaks ${pct1(op.leakage)} (${op.leaked} of ${op.suppressed}) at ${pct0(op.coverage)} coverage.`}>
          {/* y gridlines + labels */}
          {Y_TICKS.map((t) => (
            <g key={`y${t}`}>
              <line x1={PAD_L} y1={sy(t)} x2={W - PAD_R} y2={sy(t)} stroke="var(--color-line)" strokeWidth={1} />
              <text x={PAD_L - 6} y={sy(t) + 3} textAnchor="end" fontSize={9} fill="var(--color-ink-faint)" className="tabular-nums">{pct0(t)}</text>
            </g>
          ))}
          {/* x ticks + labels */}
          {X_TICKS.map((t) => (
            <text key={`x${t}`} x={sx(t)} y={H - PAD_B + 14} textAnchor="middle" fontSize={9} fill="var(--color-ink-faint)" className="tabular-nums">{pct0(t)}</text>
          ))}
          {/* ≤1% aspirational target */}
          <line x1={PAD_L} y1={sy(0.01)} x2={W - PAD_R} y2={sy(0.01)} stroke="var(--color-verified)" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
          <text x={W - PAD_R} y={sy(0.01) - 3} textAnchor="end" fontSize={8.5} fill="var(--color-verified)">≤1% target (aspirational)</text>

          {/* the frontier */}
          <polyline points={line} fill="none" stroke="var(--color-ink-soft)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

          {/* naive strawman (status: bad) */}
          <circle cx={sx(naive.coverage)} cy={sy(naive.leakage)} r={5} fill="var(--color-escalate)" stroke="var(--color-surface)" strokeWidth={2}>
            <title>{`Naive coarse envelope: ${pct1(naive.leakage)} leakage (${naive.leaked}/${naive.suppressed}) at ${pct0(naive.coverage)} coverage`}</title>
          </circle>
          <text x={sx(naive.coverage) - 8} y={sy(naive.leakage) + 3} textAnchor="end" fontSize={10} fill="var(--color-escalate)">Naive {pct0(naive.leakage)}</text>

          {/* pre-registered operating point (status: good) */}
          <circle cx={sx(op.coverage)} cy={sy(op.leakage)} r={6} fill="var(--color-verified)" stroke="var(--color-surface)" strokeWidth={2}>
            <title>{`Pre-registered operating point: ${pct1(op.leakage)} leakage (${op.leaked}/${op.suppressed}) at ${pct0(op.coverage)} coverage; 95% upper bound ${op.leakage95Upper != null ? pct1(op.leakage95Upper) : '—'}`}</title>
          </circle>
          <text x={sx(op.coverage) + 9} y={sy(op.leakage) - 5} textAnchor="start" fontSize={10} fill="var(--color-verified)">Operating point · {op.leaked}/{op.suppressed}</text>

          {/* axis captions */}
          <text x={(PAD_L + W - PAD_R) / 2} y={H - 2} textAnchor="middle" fontSize={9.5} fill="var(--color-ink-soft)">Coverage — share of queue auto-cleared</text>
          <text x={12} y={(PAD_T + H - PAD_B) / 2} textAnchor="middle" fontSize={9.5} fill="var(--color-ink-soft)" transform={`rotate(-90 12 ${(PAD_T + H - PAD_B) / 2})`}>Leakage — P(laundering | cleared)</text>
        </svg>
      </figure>

      <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">{frontier.caveat}</p>
    </section>
  )
}
