import type { TracedClaim } from '../types'

interface TracedClaimListProps {
  claims: TracedClaim[]
  // When provided, each claim shows a Remove control (the STR grounds editor). Read-only surfaces
  // (triage / verifier) omit it.
  onRemove?: (idx: number) => void
}

// One anchored/unanchored UI pattern (ADR-0022) shared by triage, verifier, and the STR grounds
// editor. Chips are neutral provenance chrome, not a trust badge; the "model judgment" label is the
// only attention signal for a claim that cites no evidence.
export function TracedClaimList({ claims, onRemove }: TracedClaimListProps) {
  if (claims.length === 0) return null
  return (
    <ul className="mt-1.5 space-y-2">
      {claims.map((c, idx) => (
        <li key={idx} className="border-l-2 border-line pl-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2 text-[13px] leading-relaxed">
              <span aria-hidden className={`mt-px shrink-0 font-mono text-[12px] ${c.anchored ? 'text-verified' : 'text-flag'}`}>
                {c.anchored ? '✓' : '⚠'}
              </span>
              <span className="text-ink">{c.text}</span>
            </div>
            {onRemove && (
              <button
                onClick={() => onRemove(idx)}
                aria-label="Remove ground"
                className="shrink-0 text-[12px] text-ink-faint hover:text-escalate"
              >
                Remove
              </button>
            )}
          </div>
          {c.anchored ? (
            <div className="mt-1 flex flex-wrap items-center gap-1 pl-6">
              {c.evidence.transactionIds.map((t) => (
                <span key={t} className="rounded border border-line bg-paper px-1.5 py-0.5 font-mono text-[10px] text-ink-soft">
                  {t}
                </span>
              ))}
              {c.evidence.firedIndicators.map((ind, i) => (
                <span key={i} title={ind} className="rounded border border-line bg-paper px-1.5 py-0.5 text-[10px] text-ink-soft">
                  indicator
                </span>
              ))}
              {c.evidence.matchedTypology && (
                <span title={c.evidence.matchedTypology} className="rounded border border-line bg-paper px-1.5 py-0.5 text-[10px] text-ink-soft">
                  typology
                </span>
              )}
              {c.evidence.citation && (
                <span title={c.evidence.citation} className="rounded border border-line bg-paper px-1.5 py-0.5 text-[10px] text-ink-soft">
                  policy
                </span>
              )}
            </div>
          ) : (
            <div className="mt-0.5 pl-6 text-[11px] font-medium text-flag">model judgment · unverified</div>
          )}
          {/* LLM semantic verdict (ADR-0013) — present only on a live semantic run; null otherwise. */}
          {c.semanticVerdict && (() => {
            const tone = c.semanticVerdict === 'supported' ? 'text-verified'
              : c.semanticVerdict === 'unsupported' ? 'text-escalate' : 'text-flag'
            const label = c.semanticVerdict === 'supported' ? '✓ evidence-supported'
              : c.semanticVerdict === 'unsupported' ? '✗ not supported by evidence' : '? support unclear'
            return (
              <div className={`mt-1 pl-6 text-[11px] font-medium ${tone}`} title={c.semanticReason ?? undefined}>
                LLM review: {label}
              </div>
            )
          })()}
        </li>
      ))}
    </ul>
  )
}
