import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import alertsFixture from '../fixtures/alerts.json'
import type { Alert, AuditEntry, DecisionTrace, GovernanceThresholds } from '../types'
import { DecisionTraceCard } from './DecisionTraceCard'

const thresholds: GovernanceThresholds = {
  review: 0.6,
  autoClear: 0.85,
  qaSample: 0.2,
  borderlineMargin: 0.1,
}

const alerts = alertsFixture as unknown as Alert[]

const trace: DecisionTrace = {
  alertId: 'HERO-002',
  generatedAt: '2026-07-06T10:00:00+08:00',
  currentRecommendation: 'escalate',
  currentConfidence: 0.91,
  routing: 'needsReview',
  formula: 'confidence = firedIndicators / totalIndicators, persisted from the served triage output',
  steps: [
    { step: 'indicatorEvaluation', label: 'Rapid pass-through activity', inputs: { matchedTypology: 'PT-01' }, result: 'fired', evidenceIds: ['TX-1'], deterministic: true },
    { step: 'confidenceComputation', label: 'Served confidence', inputs: { firedIndicatorCount: 1, totalIndicatorCount: 2 }, result: '0.91', evidenceIds: ['TX-1'], deterministic: true },
    { step: 'verifierGate', label: 'Verifier agreement', inputs: { status: 'agreed' }, result: 'agreed', evidenceIds: ['TX-1'], deterministic: false },
    { step: 'routePolicy', label: 'Queue routing policy', inputs: { autoClearThreshold: 0.85 }, result: 'needsReview', evidenceIds: ['TX-1'], deterministic: true },
    { step: 'strFilingGate', label: 'STR/goAML filing gate', inputs: { requiresHumanEscalateSignoff: true }, result: 'locked', evidenceIds: ['TX-1'], deterministic: true },
  ],
  nonClaims: ['This trace is not DeepSeek chain-of-thought and does not expose private model reasoning.'],
}

// DecisionTraceCard is now the SINGLE decision card: it folds the former DefenseCase (routing
// defense, operating point, adversarial check, STR/goAML gate, audit replay) into the observable
// trace (formula + deterministic gate table), showing the shared recommendation/confidence once.
describe('DecisionTraceCard (merged decision + defense)', () => {
  it('shows the observable gate trace AND the routing/audit defense in one card', () => {
    const alert = alerts.find((a) => a.routing === 'autoCleared')!
    const audit: AuditEntry[] = [
      { alertId: alert.alertId, event: 'autoClear', at: '2026-07-01T00:00:00+08:00', aiRecommendation: alert.triage.recommendation, confidence: alert.triage.confidence, verifierStatus: alert.triage.verifier.status },
    ]

    render(<DecisionTraceCard trace={trace} alert={alert} thresholds={thresholds} auditEntries={audit} />)

    // The trace half (formula + deterministic gates).
    expect(screen.getByText(/Decision trace/i)).toBeTruthy()
    expect(screen.getByText(/confidence = firedIndicators/i)).toBeTruthy()
    expect(screen.getByText(/Queue routing policy/i)).toBeTruthy()
    expect(screen.getByText(/not DeepSeek chain-of-thought/i)).toBeTruthy()
    // The defense half (was DefenseCase): operating point + routing defense + audit replay.
    expect(screen.getByText(/review 60%/i)).toBeTruthy()
    expect(screen.getAllByText(/Auto-clear/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/autoClear x1/i)).toBeTruthy()
    expect(screen.getByText(new RegExp(alert.triage.matchedTypology.code))).toBeTruthy()
  })

  it('keeps STR/goAML gate defense even when the observable gate trace is unavailable', () => {
    const alert = alerts.find((a) => a.triage.recommendation === 'escalate' && a.triage.strDraft)!

    render(<DecisionTraceCard trace={null} alert={alert} thresholds={thresholds} auditEntries={[]} />)

    expect(screen.getByText(/Needs review: escalation is a consequential call/i)).toBeTruthy()
    expect(screen.getByText(/goAML export is locked until analyst sign-off/i)).toBeTruthy()
    expect(screen.getByText(/Observable gate trace unavailable/i)).toBeTruthy()
  })
})
