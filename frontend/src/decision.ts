// The analyst-decision rules, mirrored from the backend so the optimistic UI and
// the mock api can't drift from the server. Keep in sync with backend/decision.py.

import type { DecisionAction, Recommendation, STRDraft } from './types'

/** Approving keeps the AI's disposition; overriding flips it. */
export function finalDispositionFor(recommendation: Recommendation, action: DecisionAction): Recommendation {
  if (action === 'approve') return recommendation
  return recommendation === 'escalate' ? 'dismiss' : 'escalate'
}

/** The STR draft after a decision (mirrors backend decision.resolve_str_draft):
 *  dismissing drops it; escalating keeps it, or replaces it with the analyst's edit. */
export function resolveStrDraft(
  finalDisposition: Recommendation,
  editedStrDraft: STRDraft | null | undefined,
  currentStrDraft: STRDraft | null,
): STRDraft | null {
  if (finalDisposition === 'dismiss') return null
  return editedStrDraft != null ? editedStrDraft : currentStrDraft
}
