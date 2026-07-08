import { describe, expect, it } from 'vitest'
import type { Alert } from './types'
import { effectiveRouting, envelopeBenignConsistent } from './routing'

const benign = [{ runningBalance: 11000 }, { runningBalance: 8000 }]
const drain = [{ runningBalance: 10200 }, { runningBalance: 200 }] // low <= 5% of peak

type Opts = {
  recommendation?: 'dismiss' | 'escalate'
  confidence?: number
  verifier?: 'agreed' | 'flagged'
  suppression?: 'suppressed' | 'similar' | null
  debate?: boolean
  blocked?: boolean
  txns?: { runningBalance: number }[]
}

// A borderline dismiss (0.7 in [0.6, 0.85)) with a benign ledger — the flip-eligible shape by default.
function mk(o: Opts = {}): Alert {
  return {
    triage: {
      recommendation: o.recommendation ?? 'dismiss',
      confidence: o.confidence ?? 0.7,
      verifier: { status: o.verifier ?? 'agreed' },
      debate: o.debate ? {} : null,
      screening: { blocked: !!o.blocked },
      suppression: o.suppression ? { status: o.suppression } : null,
    },
    transactions: o.txns ?? benign,
  } as unknown as Alert
}

describe('envelopeBenignConsistent', () => {
  it('is true when the balance never drains to ~0', () => expect(envelopeBenignConsistent(benign as never)).toBe(true))
  it('is false on the drain-to-zero pass-through tell', () => expect(envelopeBenignConsistent(drain as never)).toBe(false))
  it('is false on an empty ledger (not verifiable)', () => expect(envelopeBenignConsistent([] as never)).toBe(false))
})

describe('effectiveRouting (mirror of route_served_alert + auto_clear_policy)', () => {
  it('auto-clears a suppressed borderline dismiss with a benign envelope', () =>
    expect(effectiveRouting(mk({ suppression: 'suppressed' }))).toBe('autoCleared'))
  it('leaves the same alert for review without a suppression', () =>
    expect(effectiveRouting(mk())).toBe('needsReview'))
  it('never clears below the review threshold, even suppressed', () =>
    expect(effectiveRouting(mk({ suppression: 'suppressed', confidence: 0.5 }))).toBe('needsReview'))
  it('denies the clear when the envelope shows a drain tell', () =>
    expect(effectiveRouting(mk({ suppression: 'suppressed', txns: drain }))).toBe('needsReview'))
  it('never clears an escalate, flag, debate, or screening hit', () => {
    expect(effectiveRouting(mk({ suppression: 'suppressed', recommendation: 'escalate' }))).toBe('needsReview')
    expect(effectiveRouting(mk({ suppression: 'suppressed', verifier: 'flagged' }))).toBe('needsReview')
    expect(effectiveRouting(mk({ suppression: 'suppressed', debate: true }))).toBe('needsReview')
    expect(effectiveRouting(mk({ suppression: 'suppressed', blocked: true }))).toBe('needsReview')
  })
  it('auto-clears a high-confidence dismiss regardless of suppression', () =>
    expect(effectiveRouting(mk({ confidence: 0.9 }))).toBe('autoCleared'))
})
