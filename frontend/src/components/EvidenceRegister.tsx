import type { STRDraft, TriageResult } from '../types'

interface EvidenceRegisterProps {
  triage: TriageResult
  strDraft: STRDraft
  onFocusTransaction: (id: string) => void
}

type Support = { label: string; title: string }

const KIND_LABEL: Record<string, string> = {
  transaction: 'txn',
  indicator: 'indicator',
  policy: 'policy',
  typology: 'typology',
}

// The inverse of the anchoring (ADR-0013): every fact, and the claims that rest on it. Derived
// purely from the alert's existing trace — the grounds' anchors, the narrative figures, the fired
// indicators, the citation — so there is no new inference. The auditor's lens: if a fact does not
// hold, the claims resting on it fall with it.
export function EvidenceRegister({ triage, strDraft, onFocusTransaction }: EvidenceRegisterProps) {
  const grounds = (strDraft.tracedClaims ?? []).filter((g) => g.anchored)
  const figures = strDraft.narrativeFigures ?? []
  const cited = strDraft.citedTransactions ?? []
  const groundLabel = new Map(strDraft.groundsForSuspicion.map((g, i) => [g, `G${i + 1}`]))
  const citation = grounds.map((g) => g.evidence.citation).find(Boolean) ?? null

  const groundSupports = (pred: (g: (typeof grounds)[number]) => boolean): Support[] =>
    grounds.filter(pred).map((g) => ({ label: groundLabel.get(g.text) ?? 'G', title: g.text }))

  type Row = {
    key: string
    kind: 'transaction' | 'indicator' | 'policy' | 'typology'
    primary: string
    secondary?: string
    supports: Support[]
    txnId?: string
  }
  const rows: Row[] = []

  for (const t of cited) {
    rows.push({
      key: t.transactionId,
      kind: 'transaction',
      primary: t.transactionId,
      secondary: `${t.counterpartyName} · ${t.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} ${t.currency}`,
      txnId: t.transactionId,
      supports: [
        ...groundSupports((g) => g.evidence.transactionIds.includes(t.transactionId)),
        ...figures
          .filter((f) => f.transactionIds?.includes(t.transactionId))
          .map((f) => ({ label: 'narrative', title: `“${f.text}” in the narrative` })),
      ],
    })
  }
  // Every fired indicator underpins the Escalate call and its confidence score (ADR-0007) — that is
  // the concrete claim resting on it, even when no single ground restates its exact wording.
  const triageSupport: Support = { label: 'triage', title: 'The Escalate decision & confidence score (ADR-0007)' }
  for (const ind of triage.indicatorCoverage?.fired ?? []) {
    rows.push({
      key: `ind:${ind}`,
      kind: 'indicator',
      primary: ind,
      supports: [triageSupport, ...groundSupports((g) => g.evidence.firedIndicators.includes(ind))],
    })
  }
  if (citation) {
    rows.push({
      key: 'policy',
      kind: 'policy',
      primary: citation,
      supports: [...groundSupports((g) => !!g.evidence.citation), { label: 'action', title: 'Recommended action' }],
    })
  }
  rows.push({
    key: 'typology',
    kind: 'typology',
    primary: triage.matchedTypology.name,
    secondary: triage.matchedTypology.source,
    supports: [triageSupport, ...groundSupports((g) => !!g.evidence.matchedTypology)],
  })

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <h3 className="label">Evidence register</h3>
      <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">
        Every fact, and the claims that rest on it — if a fact doesn’t hold, its claims fall with it.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-[12px]">
          <thead>
            <tr className="border-b border-line text-ink-faint">
              <th className="py-2 pr-3 font-medium">Fact</th>
              <th className="py-2 font-medium">Rests under</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-line align-top">
                <td className="py-2.5 pr-3">
                  <div className="flex items-baseline gap-2">
                    <span className="shrink-0 rounded bg-paper px-1 py-0.5 font-mono text-[10px] text-ink-faint">
                      {KIND_LABEL[r.kind]}
                    </span>
                    {r.kind === 'transaction' ? (
                      <button
                        onClick={() => r.txnId && onFocusTransaction(r.txnId)}
                        title="Show in the transaction ledger"
                        className="font-mono text-[12px] text-ink underline-offset-2 hover:underline"
                      >
                        {r.primary}
                      </button>
                    ) : (
                      <span className="text-ink">{r.primary}</span>
                    )}
                  </div>
                  {r.secondary && <div className="mt-0.5 font-mono text-[11px] text-ink-faint">{r.secondary}</div>}
                </td>
                <td className="py-2.5">
                  {r.supports.length ? (
                    <span className="flex flex-wrap gap-1">
                      {r.supports.map((s, i) => (
                        <span
                          key={i}
                          title={s.title}
                          className="rounded border border-line bg-paper px-1.5 py-0.5 text-[11px] text-ink-soft"
                        >
                          {s.label}
                        </span>
                      ))}
                    </span>
                  ) : (
                    <span className="text-[11px] text-ink-faint">supports the filing</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
