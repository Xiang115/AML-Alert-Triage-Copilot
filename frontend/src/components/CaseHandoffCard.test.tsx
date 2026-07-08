import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { CaseHandoff } from '../types'
import { CaseHandoffCard } from './CaseHandoffCard'

const handoff: CaseHandoff = {
  alertId: 'HERO-002',
  generatedAt: '2026-07-06T10:00:00+08:00',
  sourceSystem: 'VerdictAML case handoff API',
  targetSystems: ['NICE Actimize', 'bank case-management queue', 'goAML e-filing seam'],
  caseStatusUpdate: 'escalated',
  caseNote: 'Human final disposition: escalate. AI recommended escalate at 91% confidence on PT-01.',
  decision: {
    aiRecommendation: 'escalate',
    confidence: 0.91,
    verifierStatus: 'agreed',
    finalDisposition: 'escalate',
    decisionAction: 'approve',
  },
  attachments: [
    {
      name: 'Per-alert defense case',
      endpoint: '/alerts/HERO-002/defense-case',
      available: true,
      reason: 'Evidence, controls, and audit replay are always attached.',
    },
    {
      name: 'goAML STR XML',
      endpoint: '/alerts/HERO-002/str.xml',
      available: true,
      reason: 'Unlocked after human escalate sign-off.',
    },
  ],
  auditEvents: [],
  submissionRef: null,
  writeBack: {
    mode: 'humanApprovedWriteback',
    allowed: true,
    requiresHumanDecision: true,
    productionGate: 'Enable write-back only after bank historical replay.',
  },
  nonClaims: ['This demo endpoint does not mutate a live bank case-management system.'],
}

describe('CaseHandoffCard', () => {
  it('renders the bank case-management packet and artifact states', () => {
    render(<CaseHandoffCard handoff={handoff} />)

    expect(screen.getByText(/Bank handoff/i)).toBeTruthy()
    expect(screen.getByText(/case-management write-back packet/i)).toBeTruthy()
    expect(screen.getByText(/NICE Actimize/i)).toBeTruthy()
    expect(screen.getByText(/Human final disposition: escalate/i)).toBeTruthy()
    expect(screen.getByText('humanApprovedWriteback')).toBeTruthy()
    expect(screen.getByText('/alerts/HERO-002/defense-case')).toBeTruthy()
    expect(screen.getByText('/alerts/HERO-002/str.xml')).toBeTruthy()
    expect(screen.getAllByText('attached')).toHaveLength(2)
  })

  it('shows the shadow-mode blocker before human decision', () => {
    render(
      <CaseHandoffCard
        handoff={{
          ...handoff,
          caseStatusUpdate: 'needsReview',
          writeBack: {
            ...handoff.writeBack,
            mode: 'shadowOnly',
            allowed: false,
            blockedReason: 'No analyst final disposition yet.',
          },
        }}
      />,
    )

    expect(screen.getByText('shadowOnly')).toBeTruthy()
    expect(screen.getByText(/No analyst final disposition yet/i)).toBeTruthy()
  })
})
