import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import alertsFixture from '../fixtures/alerts.json'
import type { Alert, AuditEntry, GovernanceThresholds } from '../types'
import { DefenseCase } from './DefenseCase'

const thresholds: GovernanceThresholds = {
  review: 0.6,
  autoClear: 0.85,
  qaSample: 0.2,
  borderlineMargin: 0.1,
}

const alerts = alertsFixture as unknown as Alert[]

describe('DefenseCase', () => {
  it('summarizes the evidence, routing gate, and audit replay for an auto-cleared alert', () => {
    const alert = alerts.find((a) => a.routing === 'autoCleared')!
    const audit: AuditEntry[] = [
      {
        alertId: alert.alertId,
        event: 'autoClear',
        at: '2026-07-01T00:00:00+08:00',
        aiRecommendation: alert.triage.recommendation,
        confidence: alert.triage.confidence,
        verifierStatus: alert.triage.verifier.status,
      },
    ]

    render(<DefenseCase alert={alert} thresholds={thresholds} auditEntries={audit} />)

    expect(screen.getByText(/Defense case/i)).toBeTruthy()
    expect(screen.getByText(/Auto-clear eligible/i)).toBeTruthy()
    expect(screen.getByText(/autoClear x1/i)).toBeTruthy()
    expect(screen.getByText(new RegExp(alert.triage.matchedTypology.code))).toBeTruthy()
  })

  it('keeps STR/goAML locked until analyst sign-off on an escalation', () => {
    const alert = alerts.find((a) => a.triage.recommendation === 'escalate' && a.triage.strDraft)!

    render(<DefenseCase alert={alert} thresholds={thresholds} auditEntries={[]} />)

    expect(screen.getByText(/Needs review: escalation is a consequential call/i)).toBeTruthy()
    expect(screen.getByText(/goAML export is locked until analyst sign-off/i)).toBeTruthy()
  })
})
