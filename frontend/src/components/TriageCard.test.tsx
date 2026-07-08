import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TriageCard } from './TriageCard'
import type { TriageResult } from '../types'

const triage: TriageResult = {
  alertId: 'A-1', recommendation: 'escalate', confidence: 0.8,
  matchedTypology: { code: 'PT-01', name: 'Pass-through', source: 'FATF' },
  citedTransactionIds: ['T-1'], indicatorCoverage: { indicators: ['i1'], fired: ['i1'] },
  verifier: { status: 'agreed', agreesWithRecommendation: true, claims: [] },
  claims: [{ text: 'Balance swept to ~0', anchored: true, evidence: { transactionIds: ['T-1'], firedIndicators: [] } }],
  evidenceIntegrity: { anchoredCount: 1, unanchoredCount: 0, totalCount: 1 },
  strDraft: null, model: 'm', generatedAt: '2026-07-07T00:00:00',
} as unknown as TriageResult

describe('TriageCard', () => {
  it('renders claims + evidence integrity, and drops the old explanation prose', () => {
    render(<TriageCard triage={triage}
      timeline={{ events: [], revealed: 0, playing: false }}
      onRunLive={() => {}} onReplayReasoning={() => {}} busy={false} />)
    expect(screen.getByText('Balance swept to ~0')).toBeTruthy()
    expect(screen.getByText(/1 anchored/i)).toBeTruthy()
    expect(screen.getByText(/Grounds for the call/i)).toBeTruthy()
    expect(screen.queryByText('Evidence')).toBeNull()
  })
})
