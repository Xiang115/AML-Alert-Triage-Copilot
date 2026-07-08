import type { Alert } from './types'

// Serve-time routing, mirrored from the backend so mock mode drives the SAME closed loop:
//   queue_agent.auto_clear_policy + route_served_alert + memory.envelope_benign_consistent (ADR-0021).
// A matched suppression auto-clears a BORDERLINE dismiss (below the auto-clear threshold, at/above the
// review threshold), gated by the alert's own benign-consistent ledger envelope — so dismissing one
// look-alike shrinks the worklist as its siblings self-suppress.

export const REVIEW_THRESHOLD = 0.6
export const AUTO_CLEAR_THRESHOLD = 0.85
const SWEEP_NEAR_ZERO = 0.05

// Mirror of agents.memory.envelope_benign_consistent: no drain-to-~0 pass-through tell.
export function envelopeBenignConsistent(txns: Alert['transactions']): boolean {
  if (!txns || txns.length === 0) return false
  const bals = txns.map((t) => t.runningBalance ?? 0)
  const peak = Math.max(...bals)
  const low = Math.min(...bals)
  return !(peak > 0 && low <= SWEEP_NEAR_ZERO * peak)
}

export type Routing = 'autoCleared' | 'needsReview'

// Mirror of queue_agent.route_served_alert(+auto_clear_policy). Suppression must already be attached
// to triage (as the mock's mockSuppress / the backend's enrich_served_alert does).
export function effectiveRouting(alert: Alert): Routing {
  const t = alert.triage
  if (t.debate) return 'needsReview'
  if (t.screening?.blocked) return 'needsReview'
  if (t.recommendation === 'dismiss' && t.verifier.status === 'agreed') {
    if (t.confidence >= AUTO_CLEAR_THRESHOLD) return 'autoCleared'
    const suppressed =
      t.suppression?.status === 'suppressed' && envelopeBenignConsistent(alert.transactions)
    if (suppressed && t.confidence >= REVIEW_THRESHOLD) return 'autoCleared'
  }
  return 'needsReview'
}
