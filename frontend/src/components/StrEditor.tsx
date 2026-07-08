import { useState } from 'react'
import type { STRDraft, SubmissionAck, Transaction } from '../types'
import { Badge } from './ui/Badge'
import { GoamlDefense } from './GoamlDefense'
import { TracedClaimList } from './TracedClaimList'

interface StrEditorProps {
  strDraft: STRDraft
  // The full cited transactions (alert.transactions filtered to citedTransactionIds), so the
  // Reported-transactions table shows direction/channel and matches the ledger + goAML XML.
  citedTransactions: Transaction[]
  summary: string
  onSummaryChange: (value: string) => void
  grounds: string[]
  onAddGround: (text: string) => void
  onRemoveGround: (idx: number) => void
  canExport: boolean
  onExport: () => void
  ack: SubmissionAck | null
}

const money = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2 })
// SAML-D carries no real account type; render the honest placeholder as an em dash.
const orDash = (v: string) => (v && v !== 'unknown' ? v : '—')

export function StrEditor({ strDraft, citedTransactions, summary, onSummaryChange, grounds, onAddGround, onRemoveGround, canExport, onExport, ack }: StrEditorProps) {
  const [newGroundItem, setNewGroundItem] = useState('')

  const addGroundItem = () => {
    if (newGroundItem.trim()) {
      onAddGround(newGroundItem.trim())
      setNewGroundItem('')
    }
  }

  // Evidence-Anchored STR (ADR-0013): the read-only self-review trace. Chips are neutral chrome
  // (provenance, not a trust badge); the banner is the only signal — an attention router.
  const traced = strDraft.tracedClaims ?? []
  const anchoredCount = traced.filter((c) => c.anchored).length
  const coverage = traced.length > 0 ? Math.round((anchoredCount / traced.length) * 100) : null
  // LLM semantic anchor (ADR-0013): present only on a live semantic run, else every verdict is null.
  const claimByText = new Map(traced.map((c) => [c.text, c]))
  // Unanchored grounds the analyst has not restored yet — restoring adds the text back to `grounds`.
  const stillPulled = (strDraft.unanchoredClaims ?? []).filter((t) => !grounds.includes(t))
  // Narrative figure check (ADR-0013 deepening): each amount in the AI-drafted narrative pinned to
  // the ledger value it equals, or flagged 'unmatched' (a rounding/subtotal to eyeball). Read-only.
  const figures = strDraft.narrativeFigures ?? []
  const figuresMatched = figures.filter((f) => f.kind !== 'unmatched').length
  const figuresUnmatched = figures.length - figuresMatched

  return (
    <section className="flex grow flex-col overflow-hidden rounded-lg border border-line bg-surface p-5">
      <div className="flex shrink-0 items-center justify-between">
        <h3 className="label">Suspicious transaction report</h3>
        <Badge tone="bg-paper text-ink-soft">Draft</Badge>
      </div>

      <div className="mt-4 flex grow flex-col gap-5 overflow-y-auto pr-1">
        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="label">Institution</div>
            <div className="mt-1 text-[13px] text-ink">{strDraft.reportingInstitution}</div>
          </div>
          <div>
            <div className="label">Report date</div>
            <div className="mt-1 font-mono text-[13px] text-ink">{strDraft.reportDate.substring(0, 10)}</div>
          </div>
        </div>

        {/* Report header — subject, suspected typology, period. Read-only (ADR-0006 keeps only
            the narrative + grounds editable on camera); straight from strDraft, matches goAML. */}
        <div className="rounded-md border border-line bg-paper px-3 py-2.5">
          <div className="label">Subject</div>
          <div className="mt-1 text-[13px] text-ink">{strDraft.subject.holderName}</div>
          <div className="mt-0.5 font-mono text-[12px] text-ink-soft">
            {strDraft.subject.accountId} · {orDash(strDraft.subject.accountType)} · opened{' '}
            {strDraft.subject.openedAt.substring(0, 10)}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="label">Suspected typology</div>
            <div className="mt-1 text-[13px] text-ink">
              {strDraft.typology.code} — {strDraft.typology.name}
            </div>
            <div className="mt-1">
              <Badge tone="bg-paper text-ink-soft">{strDraft.typology.source}</Badge>
            </div>
          </div>
          <div>
            <div className="label">Reporting period</div>
            <div className="mt-1 font-mono text-[13px] text-ink">
              {strDraft.period.from.substring(0, 10)} → {strDraft.period.to.substring(0, 10)}
            </div>
          </div>
        </div>

        {/* Narrative — fixed height now that the report sections below fill the panel. */}
        <div className="flex flex-col">
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="label">Narrative</span>
            <span className="text-[11px] text-ink-faint">Drafted by AI · editable</span>
          </div>
          <textarea
            value={summary}
            onChange={(e) => onSummaryChange(e.target.value)}
            rows={5}
            className="w-full resize-y rounded-md border border-line bg-surface p-3 text-[13px] leading-relaxed text-ink outline-none focus:border-ink min-h-[7rem]"
          />

          {/* Figure check — every amount in the narrative pinned to its exact ledger value (ADR-0013). */}
          {figures.length > 0 && (
            <div className="mt-2">
              <div className="mb-1 text-[11px] text-ink-faint">
                Figure check — {figuresMatched} of {figures.length} narrative figures tie to an exact ledger value
                {figuresUnmatched > 0 && ` · ${figuresUnmatched} approx/subtotal — verify`}
              </div>
              <ul className="flex flex-wrap gap-1.5">
                {figures.map((f, i) =>
                  f.kind === 'unmatched' ? (
                    <li
                      key={i}
                      title="Not an exact transaction, subtotal, or balance — likely a rounding or partial subtotal; verify before filing"
                      className="rounded border border-flag px-1.5 py-0.5 font-mono text-[11px] text-flag"
                    >
                      {f.text} · approx
                    </li>
                  ) : (
                    <li
                      key={i}
                      title={
                        f.kind === 'transaction'
                          ? `matches transaction ${f.transactionIds.join(', ')}`
                          : f.kind === 'balance'
                            ? 'matches a running balance'
                            : 'matches the sum of the transactions'
                      }
                      className="rounded border border-line bg-paper px-1.5 py-0.5 font-mono text-[11px] text-ink-soft"
                    >
                      {f.text}
                      <span className="ml-1 text-ink-faint">
                        → {f.kind === 'transaction' ? f.transactionIds[0] : f.kind}
                      </span>
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}
        </div>

        {/* Reported transactions — the cited legs being filed (read-only). Full transactions so
            direction shows; mirrors the goAML <transaction> list. */}
        {citedTransactions.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="label">Reported transactions</span>
              <span className="text-[11px] text-ink-faint">{citedTransactions.length} filed · read-only</span>
            </div>
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-line text-ink-faint">
                  <th className="py-1.5 pr-2 font-medium">Date</th>
                  <th className="py-1.5 pr-2 font-medium">Dir</th>
                  <th className="py-1.5 pr-2 font-medium">Counterparty</th>
                  <th className="py-1.5 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {citedTransactions.map((t) => (
                  <tr key={t.transactionId} className="border-b border-line align-top last:border-0">
                    <td className="py-1.5 pr-2 font-mono text-ink-soft">{t.timestamp.substring(0, 10)}</td>
                    <td className="py-1.5 pr-2">
                      <span className={t.direction === 'inbound' ? 'text-verified' : 'text-ink-soft'}>
                        {t.direction === 'inbound' ? 'in' : 'out'}
                      </span>
                    </td>
                    <td className="py-1.5 pr-2 text-ink">{t.counterpartyName}</td>
                    <td className="py-1.5 text-right font-mono tabular-nums text-ink">
                      {money(t.amount)} {t.currency}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Grounds for suspicion — Evidence-Anchored STR (ADR-0013) */}
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="label">Grounds for suspicion</span>
            <span className="text-[11px] text-ink-faint">Evidence-anchored · editable</span>
          </div>

          {/* Self-review banner: an attention router, not a trust badge. */}
          {traced.length > 0 && (
            <div
              className={`mb-2 rounded-md border px-3 py-2 text-[12px] ${
                stillPulled.length > 0
                  ? 'border-flag bg-flag-soft text-flag'
                  : 'border-verified bg-verified-soft text-verified'
              }`}
            >
              {stillPulled.length > 0 ? (
                <>
                  Self-review traced <b>{anchoredCount} of {traced.length}</b> AI claims to evidence —{' '}
                  <b>{stillPulled.length}</b> could not be traced, so it was pulled from the filed draft. Verify before filing.
                </>
              ) : (
                <>Self-review traced <b>all {traced.length}</b> AI claims to evidence.</>
              )}
              {coverage !== null && <span className="ml-1 opacity-70">· {coverage}% coverage</span>}
            </div>
          )}

          {(() => {
            // Map each filed ground to its traced claim (evidence + anchored + semantic verdict);
            // an analyst-added ground with no trace renders as an unanchored claim.
            const filed = grounds.map(
              (g) => claimByText.get(g) ?? { text: g, anchored: false, evidence: { transactionIds: [], firedIndicators: [] } },
            )
            return <TracedClaimList claims={filed} onRemove={onRemoveGround} />
          })()}

          <div className="mt-2 flex gap-2">
            <input
              type="text"
              value={newGroundItem}
              onChange={(e) => setNewGroundItem(e.target.value)}
              placeholder="Add a ground…"
              onKeyDown={(e) => e.key === 'Enter' && addGroundItem()}
              className="grow rounded-md border border-line bg-surface px-3 py-1.5 text-[13px] text-ink outline-none placeholder:text-ink-faint focus:border-ink"
            />
            <button
              onClick={addGroundItem}
              className="rounded-md border border-line px-3 text-[13px] font-medium text-ink-soft hover:border-ink hover:text-ink"
            >
              Add
            </button>
          </div>

          {/* Pulled from the filed draft: demote-not-delete, one-click recoverable (ADR-0013). */}
          {stillPulled.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-[12px] font-medium text-flag">
                Pulled from draft by self-review ({stillPulled.length}) — untraceable to evidence
              </summary>
              <ul className="mt-1.5 space-y-1">
                {stillPulled.map((t, i) => (
                  <li key={i} className="flex items-start justify-between gap-3 border-l-2 border-line pl-3">
                    <span className="text-[12px] leading-relaxed text-ink-faint line-through">{t}</span>
                    <button
                      onClick={() => onAddGround(t)}
                      className="shrink-0 text-[12px] font-medium text-ink-soft hover:text-ink"
                    >
                      Restore
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>

        {/* Recommended action */}
        <div>
          <div className="label">Recommended action</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{strDraft.recommendedAction}</p>
        </div>
      </div>

      {/* goAML export — the integration seam. Unlocks only after an escalate sign-off. */}
      <GoamlDefense
        canExport={canExport}
        ack={ack}
        onExport={onExport}
        citedTransactionCount={citedTransactions.length}
        anchoredClaimCount={anchoredCount}
        totalClaimCount={traced.length}
        pulledClaimCount={stillPulled.length}
      />
    </section>
  )
}
