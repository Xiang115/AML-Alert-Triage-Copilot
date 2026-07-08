import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { DecisionTrace } from '../types'
import { DecisionTraceCard } from './DecisionTraceCard'

const trace: DecisionTrace = {
  alertId: 'HERO-002',
  generatedAt: '2026-07-06T10:00:00+08:00',
  currentRecommendation: 'escalate',
  currentConfidence: 0.91,
  routing: 'needsReview',
  formula: 'confidence = firedIndicators / totalIndicators, persisted from the served triage output',
  steps: [
    {
      step: 'indicatorEvaluation',
      label: 'Rapid pass-through activity',
      inputs: { matchedTypology: 'PT-01' },
      result: 'fired',
      evidenceIds: ['TX-1'],
      deterministic: true,
    },
    {
      step: 'confidenceComputation',
      label: 'Served confidence',
      inputs: { firedIndicatorCount: 1, totalIndicatorCount: 2 },
      result: '0.91',
      evidenceIds: ['TX-1'],
      deterministic: true,
    },
    {
      step: 'verifierGate',
      label: 'Verifier agreement',
      inputs: { status: 'agreed' },
      result: 'agreed',
      evidenceIds: ['TX-1'],
      deterministic: false,
    },
    {
      step: 'routePolicy',
      label: 'Queue routing policy',
      inputs: { autoClearThreshold: 0.85 },
      result: 'needsReview',
      evidenceIds: ['TX-1'],
      deterministic: true,
    },
    {
      step: 'strFilingGate',
      label: 'STR/goAML filing gate',
      inputs: { requiresHumanEscalateSignoff: true },
      result: 'locked',
      evidenceIds: ['TX-1'],
      deterministic: true,
    },
  ],
  nonClaims: ['This trace is not DeepSeek chain-of-thought and does not expose private model reasoning.'],
}

describe('DecisionTraceCard', () => {
  it('renders observable decision gates without claiming LLM chain-of-thought', () => {
    render(<DecisionTraceCard trace={trace} />)

    expect(screen.getByText(/Decision trace/i)).toBeTruthy()
    expect(screen.getByText(/Observable system path/i)).toBeTruthy()
    expect(screen.getByText('escalate')).toBeTruthy()
    expect(screen.getByText('91%')).toBeTruthy()
    expect(screen.getByText(/confidence = firedIndicators/i)).toBeTruthy()
    expect(screen.getByText(/Verifier agreement/i)).toBeTruthy()
    expect(screen.getByText(/Queue routing policy/i)).toBeTruthy()
    expect(screen.getByText(/STR\/goAML filing gate/i)).toBeTruthy()
    expect(screen.getByText(/not DeepSeek chain-of-thought/i)).toBeTruthy()
  })

  it('shows unavailable state', () => {
    render(<DecisionTraceCard trace={null} />)

    expect(screen.getByText(/Observable decision trace unavailable/i)).toBeTruthy()
  })
})
