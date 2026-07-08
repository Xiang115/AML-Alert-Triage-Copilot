import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PilotAdoptionPlan } from './PilotAdoptionPlan'
import type { PilotAdoptionPlan as PilotAdoptionPlanData } from '../types'

const plan: PilotAdoptionPlanData = {
  mode: 'bankPilot',
  targetSegments: ['Malaysia/APAC mid-sized banks with high alert queues.', 'Digital banks and payment providers.'],
  buyerStakeholders: ['Compliance / MLRO owner', 'Model risk management', 'Information security', 'Procurement and legal'],
  pilotEconomics: {
    monthlyAlerts: 5000,
    currentReviewMinutesPerAlert: 12,
    assistedReviewMinutesPerAlert: 7,
    qaSampleMinutesPerAlert: 5,
    estimatedMonthlyHoursSaved: 360,
    valueHypothesis: 'A conservative 5-minute handling reduction can recover analyst hours.',
    caveat: 'Pilot economics are a validation target, not a production claim.',
  },
  sensitivityCases: [
    { monthlyAlerts: 1000, minutesSavedPerAlert: 3, estimatedMonthlyHoursReturned: 50, caveat: 'Low-volume pilot case.' },
    { monthlyAlerts: 5000, minutesSavedPerAlert: 5, estimatedMonthlyHoursReturned: 417, caveat: 'Mid-market operating case.' },
    { monthlyAlerts: 20000, minutesSavedPerAlert: 8, estimatedMonthlyHoursReturned: 2667, caveat: 'Scale case.' },
  ],
  commercialModel: [
    {
      name: 'Paid shadow pilot',
      customerStage: 'Historical replay and shadow validation',
      pricingModel: 'Fixed pilot fee.',
      includes: ['Validation dossier.'],
      conversionGate: 'Compliance and model-risk owners accept success criteria.',
    },
    {
      name: 'Production assist',
      customerStage: 'Live triage with human-owned decisions',
      pricingModel: 'Annual platform fee plus alert-volume tier.',
      includes: ['Queue triage.'],
      conversionGate: 'Security, legal, and operations sign off.',
    },
    {
      name: 'Governed automation',
      customerStage: 'Limited auto-clear after bank validation',
      pricingModel: 'Enterprise/private deployment tier.',
      includes: ['Approved auto-clear thresholds.'],
      conversionGate: 'Shadow pilot shows acceptable leakage.',
    },
  ],
  competitivePositioning: [
    'VerdictAML is an overlay after existing transaction monitoring, not a replacement for the bank rule engine.',
  ],
  pilotTimeline: [
    { week: 'Weeks 1-2', objective: 'Map fields.', owner: 'IT / security', evidence: '/integration/contract' },
    { week: 'Weeks 3-5', objective: 'Run historical replay.', owner: 'Model risk', evidence: '/governance/validation-dossier' },
    { week: 'Weeks 6-7', objective: 'Run shadow pilot.', owner: 'AML operations', evidence: 'Weekly readiness summaries.' },
    { week: 'Week 8', objective: 'Decide rollout.', owner: 'Compliance / procurement', evidence: 'Business case.' },
  ],
  phases: [
    {
      name: 'Read-only historical replay',
      objective: 'Run on historical alerts without touching workflow.',
      exitCriteria: ['Known outcomes loaded.', 'No automation enabled.'],
      evidenceProduced: ['Validation dossier on bank data.', 'Threshold recommendation with leakage.'],
    },
    {
      name: 'Shadow pilot',
      objective: 'Run beside analysts while the bank workflow remains authoritative.',
      exitCriteria: ['Override reasons reviewed.', 'Auto-clear leakage within tolerance.'],
      evidenceProduced: ['Weekly readiness summaries.', 'False-clear QA review pack.'],
    },
  ],
  successCriteria: ['Recall and leakage measured against bank-known outcomes.'],
  validationEvidence: [
    'Market pain: Nasdaq 2024 Global Financial Crime Report.',
    'Adoption constraint: Federal Reserve SR 11-7 model-risk validation.',
    '/metrics',
    '/finals/evidence-bundle',
  ],
  procurementRisks: ['Bank procurement and security review can take months, not days.'],
  nonClaims: ['No claim of immediate annual contract after a short pilot.', 'No unattended STR filing or escalation.'],
}

describe('PilotAdoptionPlan', () => {
  it('shows a conservative bank pilot sequence', () => {
    render(<PilotAdoptionPlan plan={plan} />)

    expect(screen.getByText(/Pilot adoption plan/i)).toBeTruthy()
    expect(screen.getByText(/conservative procurement/i)).toBeTruthy()
    expect(screen.getByText(/Read-only historical replay/i)).toBeTruthy()
    expect(screen.getAllByText(/Shadow pilot/i).length).toBeGreaterThan(0)
  })

  it('shows conservative pilot economics as a validation target', () => {
    render(<PilotAdoptionPlan plan={plan} />)

    expect(screen.getByText('Pilot economics')).toBeTruthy()
    expect(screen.getByText('validation target')).toBeTruthy()
    expect(screen.getByText('360h')).toBeTruthy()
    expect(screen.getByText(/not a production claim/i)).toBeTruthy()
    expect(screen.getByText('Sensitivity cases')).toBeTruthy()
    expect(screen.getByText('2,667h')).toBeTruthy()
  })

  it('shows commercial model, positioning, and timeline without claiming interviews', () => {
    render(<PilotAdoptionPlan plan={plan} />)

    expect(screen.getByText('Beachhead segment')).toBeTruthy()
    expect(screen.getByText(/Malaysia\/APAC/i)).toBeTruthy()
    expect(screen.getByText('Commercial model')).toBeTruthy()
    expect(screen.getByText('Paid shadow pilot')).toBeTruthy()
    expect(screen.getByText('Production assist')).toBeTruthy()
    expect(screen.getByText('Governed automation')).toBeTruthy()
    expect(screen.getByText('Positioning')).toBeTruthy()
    expect(screen.getByText(/not a replacement/i)).toBeTruthy()
    expect(screen.getByText('8-week pilot timeline')).toBeTruthy()
    expect(screen.getByText('Week 8')).toBeTruthy()
  })

  it('states procurement risks and non-claims', () => {
    render(<PilotAdoptionPlan plan={plan} />)

    expect(screen.getByText(/can take months, not days/i)).toBeTruthy()
    expect(screen.getByText(/No claim of immediate annual contract/i)).toBeTruthy()
    expect(screen.getByText(/No unattended STR filing/i)).toBeTruthy()
  })

  it('shows evidence supporting the market adoption claim', () => {
    render(<PilotAdoptionPlan plan={plan} />)

    expect(screen.getByText('Evidence basis')).toBeTruthy()
    expect(screen.getByText(/Nasdaq 2024 Global Financial Crime Report/i)).toBeTruthy()
    expect(screen.getByText(/Federal Reserve SR 11-7/i)).toBeTruthy()
  })
})
