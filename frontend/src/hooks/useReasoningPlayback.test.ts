import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { buildReasoningEvents, useReasoningPlayback } from './useReasoningPlayback'
import type { STRDraft, TriageResult } from '../types'

const triage = (over: Partial<TriageResult> = {}): TriageResult => ({
  alertId: 'X',
  recommendation: 'escalate',
  confidence: 0.75,
  explanation: 'why',
  matchedTypology: { code: 'FI-01', name: 'Fan-in / Fan-out', source: 'FATF' },
  citedTransactionIds: [],
  indicatorCoverage: { indicators: ['a', 'b', 'c', 'd'], fired: ['a', 'b', 'c'] },
  verifier: { status: 'flagged', agreesWithRecommendation: false, note: 'looks like a merchant' },
  strDraft: {} as unknown as STRDraft,
  model: 'm',
  generatedAt: '2026-01-01T00:00:00Z',
  ...over,
})

describe('buildReasoningEvents', () => {
  it('orders the pipeline stages and fires indicators one-by-one', () => {
    const ev = buildReasoningEvents(triage())
    expect(ev.filter((e) => e.kind === 'stage').map((e) => (e.kind === 'stage' ? e.id : ''))).toEqual([
      'retrieve',
      'triage',
      'verifier',
      'confidence',
      'draft',
    ])
    const inds = ev.filter((e) => e.kind === 'indicator')
    expect(inds).toHaveLength(4)
    expect(inds.filter((i) => i.kind === 'indicator' && i.fired)).toHaveLength(3)

    const retrieve = ev.find((e) => e.kind === 'stage' && e.id === 'retrieve')
    expect(retrieve && retrieve.kind === 'stage' && retrieve.label).toContain('ranking')

    const verifier = ev.find((e) => e.kind === 'stage' && e.id === 'verifier')
    expect(verifier && verifier.kind === 'stage' && verifier.detail).toContain('FLAGGED')
    expect(verifier && verifier.kind === 'stage' && verifier.detail).toContain('looks like a merchant')

    const conf = ev.find((e) => e.kind === 'stage' && e.id === 'confidence')
    expect(conf && conf.kind === 'stage' && conf.detail).toContain('3/4')
    // A flagged ESCALATE is not capped (ADR-0007) — the disagreement, not a low score, forces review.
    expect(conf && conf.kind === 'stage' && conf.detail).not.toContain('capped')
  })

  it('inserts the debate turns (challenge → rebuttal → re-verdict) after the verifier when present', () => {
    const ev = buildReasoningEvents(
      triage({
        debate: {
          challenge: { counterHypothesis: 'legitimate merchant', distinguishingTestAssessment: 'funds dwell over a day' },
          rebuttal: { argument: 'senders are unrelated individuals', conceded: false },
          reverdict: { outcome: 'holds', dispositionChanged: false, note: 'the flag stands — refer to a human' },
        },
      }),
    )
    expect(ev.filter((e) => e.kind === 'stage').map((e) => (e.kind === 'stage' ? e.id : ''))).toEqual([
      'retrieve',
      'triage',
      'verifier',
      'challenge',
      'rebuttal',
      'reverdict',
      'confidence',
      'draft',
    ])
    const rev = ev.find((e) => e.kind === 'stage' && e.id === 'reverdict')
    expect(rev && rev.kind === 'stage' && rev.detail).toContain('the flag stands')
  })

  it('inserts a grounding beat after the indicators when transactions are cited', () => {
    const ev = buildReasoningEvents(triage({ citedTransactionIds: ['T-1', 'T-2'] }))
    expect(ev.filter((e) => e.kind === 'stage').map((e) => (e.kind === 'stage' ? e.id : ''))).toEqual([
      'retrieve',
      'triage',
      'grounding',
      'verifier',
      'confidence',
      'draft',
    ])
    const grounding = ev.find((e) => e.kind === 'stage' && e.id === 'grounding')
    expect(grounding && grounding.kind === 'stage' && grounding.detail).toContain('2 cited transactions verified against the account ledger')
  })

  it('omits the grounding beat when nothing is cited', () => {
    const ev = buildReasoningEvents(triage({ citedTransactionIds: [] }))
    expect(ev.some((e) => e.kind === 'stage' && e.id === 'grounding')).toBe(false)
  })

  it('handles a no-match dismiss (no indicators, STR skipped)', () => {
    const ev = buildReasoningEvents(
      triage({
        recommendation: 'dismiss',
        matchedTypology: { code: 'NONE', name: 'No typology matched', source: '—' },
        indicatorCoverage: { indicators: [], fired: [] },
        verifier: { status: 'agreed', agreesWithRecommendation: true, note: 'no pattern' },
        strDraft: null,
      }),
    )
    expect(ev.filter((e) => e.kind === 'indicator')).toHaveLength(0)
    const retrieve = ev.find((e) => e.kind === 'stage' && e.id === 'retrieve')
    expect(retrieve && retrieve.kind === 'stage' && retrieve.detail).toContain('No candidate typology')
    const draft = ev.find((e) => e.kind === 'stage' && e.id === 'draft')
    expect(draft && draft.kind === 'stage' && draft.detail).toContain('Skipped')
  })
})

describe('useReasoningPlayback', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('reveals events over time then stops playing', () => {
    const { result } = renderHook(() => useReasoningPlayback())
    act(() => result.current.play(triage()))
    expect(result.current.playing).toBe(true)
    act(() => vi.advanceTimersByTime(10000))
    expect(result.current.revealed).toBe(result.current.events.length)
    expect(result.current.playing).toBe(false)
  })

  it('reset() clears state', () => {
    const { result } = renderHook(() => useReasoningPlayback())
    act(() => result.current.play(triage()))
    act(() => result.current.reset())
    expect(result.current.revealed).toBe(0)
    expect(result.current.playing).toBe(false)
    expect(result.current.events).toEqual([])
  })
})
