import { useCallback, useRef, useState } from 'react'
import type { TriageResult } from '../types'

export type ReasoningEvent =
  | { kind: 'stage'; id: string; label: string; detail: string; tone?: 'escalate' | 'flag' | 'verified' }
  | { kind: 'indicator'; text: string; fired: boolean }

/**
 * Flatten a triage result into the ordered "thinking" steps the pipeline took, so the
 * UI can reveal the agent's reasoning step-by-step (retrieve → triage → indicators →
 * verifier → confidence → draft) instead of snapping straight to the answer. Pure —
 * unit-tested, and shared by the precomputed replay and the live run.
 */
export function buildReasoningEvents(t: TriageResult): ReasoningEvent[] {
  const ev: ReasoningEvent[] = []
  const matched = t.matchedTypology.code !== 'NONE' && t.indicatorCoverage.indicators.length > 0

  ev.push({
    kind: 'stage',
    id: 'retrieve',
    // The live run ranks all candidates by signal overlap; the replay reconstructs from the
    // stored result, so it frames the matched card as the strongest retrieved candidate.
    label: 'Retrieving & ranking typology cards (FATF / BNM)',
    detail: matched
      ? `Matched ${t.matchedTypology.code} — ${t.matchedTypology.name} · ${t.matchedTypology.source}`
      : 'No candidate typology matched the evidence',
  })

  ev.push({
    kind: 'stage',
    id: 'triage',
    label: 'Triage agent — assessing the call',
    detail: `${t.recommendation === 'escalate' ? 'Escalate' : 'Dismiss'} — matched ${t.matchedTypology.code} ${t.matchedTypology.name}. ${t.evidenceIntegrity?.anchoredCount ?? 0}/${t.evidenceIntegrity?.totalCount ?? 0} grounds evidence-anchored.`,
    tone: t.recommendation === 'escalate' ? 'escalate' : 'verified',
  })

  const firedSet = new Set(t.indicatorCoverage.fired)
  for (const ind of t.indicatorCoverage.indicators) {
    ev.push({ kind: 'indicator', text: ind, fired: firedSet.has(ind) })
  }

  // Citation Grounding: every cited id is a real ledger entry (clamped server-side). Surface
  // it as a reasoning beat — only when the call cited anything. The precomputed citations are
  // all valid, so this mirrors the live grounding stage's "all verified, none dropped" case.
  const citedCount = t.citedTransactionIds.length
  if (citedCount > 0) {
    ev.push({
      kind: 'stage',
      id: 'grounding',
      label: 'Grounding citations against the source ledger',
      detail: `${citedCount} cited transaction${citedCount === 1 ? '' : 's'} verified against the account ledger`,
      tone: 'verified',
    })
  }

  ev.push({
    kind: 'stage',
    id: 'verifier',
    label: 'Adversarial verifier — challenging the call',
    detail: `${t.verifier.status === 'flagged' ? 'FLAGGED for human review' : 'Agreed'} — ${t.verifier.claims?.length ?? 0} ground(s) assessed`,
    tone: t.verifier.status === 'flagged' ? 'flag' : 'verified',
  })

  // Adversarial debate (ADR-0011): present only on a flagged first pass. Mirrors the
  // backend SSE stream so the precomputed replay and the live run show the same turns.
  if (t.debate) {
    const { challenge, rebuttal, reverdict } = t.debate
    ev.push({
      kind: 'stage',
      id: 'challenge',
      label: "Adversarial debate — the verifier's challenge",
      detail: `${challenge.counterHypothesis} ${challenge.distinguishingTestAssessment}`,
      tone: 'flag',
    })
    ev.push({
      kind: 'stage',
      id: 'rebuttal',
      label: 'Triage rebuttal',
      detail: `${rebuttal.conceded ? 'Conceded — ' : 'Defends the call — '}${rebuttal.argument}`,
      tone: rebuttal.conceded ? 'verified' : 'escalate',
    })
    const reverdictDetail = {
      holds: `Flag holds — ${reverdict.note}`,
      convinced: `Verifier convinced; flag resolved — ${reverdict.note}`,
      conceded: reverdict.note,
    }[reverdict.outcome]
    ev.push({
      kind: 'stage',
      id: 'reverdict',
      label: 'Verifier re-verdict',
      detail: reverdictDetail,
      tone: reverdict.outcome === 'holds' ? 'flag' : 'verified',
    })
  }

  const total = t.indicatorCoverage.indicators.length
  const pct = Math.round(t.confidence * 100)
  ev.push({
    kind: 'stage',
    id: 'confidence',
    label: 'Computing confidence from indicator coverage',
    detail:
      total > 0
        ? `${t.indicatorCoverage.fired.length}/${total} indicators fired → ${pct}%` +
          (t.verifier.status === 'flagged' && t.recommendation === 'dismiss'
            ? ' (capped below review threshold)'
            : '')
        : `${pct}% — no pattern to score`,
  })

  ev.push({
    kind: 'stage',
    id: 'draft',
    label: 'STR drafter',
    detail: t.strDraft
      ? 'Structured Suspicious Transaction Report drafted'
      : 'Skipped — no report drafted on a dismiss',
  })

  return ev
}

const STAGE_MS = 650
const INDICATOR_MS = 280

export interface ReasoningPlayback {
  events: ReasoningEvent[]
  revealed: number // how many events are currently visible
  playing: boolean
  play: (triage: TriageResult) => void
  reset: () => void
}

/** Reveals the reasoning events one-by-one on a timer (the "thinking" animation). */
export function useReasoningPlayback(): ReasoningPlayback {
  const [events, setEvents] = useState<ReasoningEvent[]>([])
  const [revealed, setRevealed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const clearTimers = () => {
    timers.current.forEach(clearTimeout)
    timers.current = []
  }

  const reset = useCallback(() => {
    clearTimers()
    setPlaying(false)
    setRevealed(0)
    setEvents([])
  }, [])

  const play = useCallback((triage: TriageResult) => {
    clearTimers()
    const ev = buildReasoningEvents(triage)
    setEvents(ev)
    setRevealed(0)
    setPlaying(true)
    let at = 0
    ev.forEach((e, i) => {
      at += e.kind === 'indicator' ? INDICATOR_MS : STAGE_MS
      const timer = setTimeout(() => {
        setRevealed(i + 1)
        if (i === ev.length - 1) setPlaying(false)
      }, at)
      timers.current.push(timer)
    })
  }, [])

  return { events, revealed, playing, play, reset }
}
