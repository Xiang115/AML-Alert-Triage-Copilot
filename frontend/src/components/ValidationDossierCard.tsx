import type { ValidationDossier } from '../types'

const pct = (v: number | null | undefined) => (v == null ? '-' : `${Math.round(v * 100)}%`)

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-paper px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="mt-1 font-mono text-[16px] font-semibold tabular-nums text-ink">{value}</div>
    </div>
  )
}

function BulletList({ items, tone }: { items: string[]; tone: 'verified' | 'flag' }) {
  const marker = tone === 'verified' ? '+' : '!'
  const markerClass = tone === 'verified' ? 'text-verified' : 'text-flag'
  return (
    <ul className="mt-2 space-y-1.5">
      {items.map((item) => (
        <li key={item} className="flex gap-2 text-[12px] leading-relaxed text-ink-soft">
          <span aria-hidden className={`shrink-0 font-mono ${markerClass}`}>
            {marker}
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

export function ValidationDossierCard({ dossier }: { dossier: ValidationDossier | null }) {
  if (!dossier) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Validation dossier</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Validation dossier unavailable.</div>
      </section>
    )
  }

  const totalTypologies = dossier.measuredTypologies.length + dossier.roadmapTypologies.length

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="label">Validation dossier</h3>
          <p className="mt-1 text-[12px] text-ink-faint">
            {dossier.dataset} | n={dossier.n} | {dossier.model ?? 'model pending'}
          </p>
        </div>
        <span className="rounded border border-flag bg-flag-soft px-2 py-1 text-[11px] font-medium text-flag">
          {dossier.productionState === 'shadowOnly' ? 'shadow only' : dossier.productionState}
        </span>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-4">
        <Metric label="Recall" value={pct(dossier.recall)} />
        <Metric label="Precision" value={pct(dossier.precision)} />
        <Metric label="Accuracy" value={pct(dossier.accuracyVsLabels)} />
        <Metric label="Leakage" value={pct(dossier.autoClearLeakageRate)} />
      </div>

      <div className="mt-4 rounded-md border border-line bg-paper p-3">
        <div className="label">Baseline answer</div>
        <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{dossier.baselineExplanation}</p>
        <div className="mt-2 grid gap-2 text-[12px] text-ink-soft md:grid-cols-3">
          <span>
            Baseline <span className="font-mono text-ink">{pct(dossier.baselineAccuracy)}</span>
          </span>
          <span>
            Auto-cleared reports{' '}
            <span className="font-mono text-ink">
              {dossier.autoClearedReports ?? '-'}/{dossier.totalReports ?? '-'}
            </span>
          </span>
          <span>
            CM{' '}
            <span className="font-mono text-ink">
              TP {dossier.confusionMatrix.tp} / FP {dossier.confusionMatrix.fp} / FN {dossier.confusionMatrix.fn} / TN{' '}
              {dossier.confusionMatrix.tn}
            </span>
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <div className="label">Release gates</div>
          <BulletList items={dossier.releaseGates} tone="verified" />
        </div>
        <div>
          <div className="label">Still prohibited</div>
          <BulletList items={dossier.prohibitedActions} tone="flag" />
        </div>
      </div>

      <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-faint">
        Coverage: {dossier.measuredTypologies.length} of {totalTypologies} curated typologies measured (
        {dossier.measuredTypologies.join(', ') || '-'}); roadmap: {dossier.roadmapTypologies.join(', ') || '-'}.
      </p>
    </section>
  )
}
