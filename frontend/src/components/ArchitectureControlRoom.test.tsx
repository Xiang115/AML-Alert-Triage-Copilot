import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ArchitectureControlRoom } from './ArchitectureControlRoom'
import type { ReadinessSummary, TechnicalArchitecture } from '../types'

const architecture: TechnicalArchitecture = {
  mode: 'technicalArchitecture',
  thesis: 'VerdictAML is an end-to-end AML control workflow.',
  components: [
    {
      id: 'bank-monitoring',
      name: 'Existing bank monitoring engine',
      layer: 'bank',
      responsibility: 'Emits alert id, account, and ledger window.',
      proofEndpoints: ['/integration/contract'],
    },
    {
      id: 'api-store',
      name: 'FastAPI service and relational store',
      layer: 'api',
      responsibility: 'Persists alerts, decisions, and audit events.',
      proofEndpoints: ['/health', '/alerts'],
    },
    {
      id: 'triage-agents',
      name: 'Triage and verifier agents',
      layer: 'agent',
      responsibility: 'Generate and challenge decisions.',
      proofEndpoints: ['/alerts/HERO-002/defense-case'],
    },
    {
      id: 'control-plane',
      name: 'Deterministic control plane',
      layer: 'control',
      responsibility: 'Applies thresholds, QA sampling, and filing gates.',
      proofEndpoints: ['/governance/validation-dossier', '/readiness/summary'],
    },
    {
      id: 'analyst-ui',
      name: 'Reviewer console',
      layer: 'ui',
      responsibility: 'Shows queue, evidence, audit, and governance.',
      proofEndpoints: ['/finals/evidence-bundle'],
    },
  ],
  flows: [
    {
      source: 'bank-monitoring',
      target: 'api-store',
      payload: 'Alert metadata plus ledger window.',
      control: 'Input schema validation rejects malformed alerts.',
    },
    {
      source: 'triage-agents',
      target: 'control-plane',
      payload: 'Recommendation, confidence, verifier, and screening result.',
      control: 'Deterministic gates override model confidence.',
    },
    {
      source: 'control-plane',
      target: 'analyst-ui',
      payload: 'Routing decision, QA flag, and blocked reason.',
      control: 'Auto-clear is limited to verifier-agreed dismissals.',
    },
  ],
  dataHandling: ['Queue rows omit embedded transactions.'],
  aiExecution: ['Verifier challenges the first-pass decision.'],
  reliabilityControls: ['Readiness validates contracts.'],
  demoPath: ['Open Governance.'],
  caveat: 'Production requires bank replay.',
}

const readiness: ReadinessSummary = {
  status: 'pass',
  checkedAt: '2026-07-06T10:00:00+08:00',
  checks: [
    { name: 'contract /architecture/technical', endpoint: '/architecture/technical', ok: true, detail: 'ok' },
    { name: 'contract /integration/contract', endpoint: '/integration/contract', ok: true, detail: 'ok' },
    { name: 'contract /queue/briefing', endpoint: '/queue/briefing', ok: true, detail: 'ok' },
    { name: 'contract /operations/impact', endpoint: '/operations/impact', ok: true, detail: 'ok' },
    { name: 'contract /governance/validation-dossier', endpoint: '/governance/validation-dossier', ok: true, detail: 'ok' },
    { name: 'contract /finals/evidence-bundle', endpoint: '/finals/evidence-bundle', ok: true, detail: 'ok' },
    { name: 'contract /alerts/HERO-002/defense-case', endpoint: '/alerts/HERO-002/defense-case', ok: true, detail: 'ok' },
  ],
}

describe('ArchitectureControlRoom', () => {
  it('visualizes the live architecture lanes, controls, and proof endpoints', () => {
    render(<ArchitectureControlRoom architecture={architecture} readiness={readiness} />)

    expect(screen.getByText(/Architecture control room/i)).toBeTruthy()
    expect(screen.getByText(/Bank systems/i)).toBeTruthy()
    expect(screen.getByText(/API \+ store/i)).toBeTruthy()
    expect(screen.getByText(/AI workbench/i)).toBeTruthy()
    expect(screen.getAllByText(/Control plane/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Reviewer console/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Deterministic gates override model confidence/i).length).toBeGreaterThan(0)
    expect(screen.getByText('/finals/evidence-bundle')).toBeTruthy()
    expect(screen.getByText('/architecture/technical')).toBeTruthy()
    expect(screen.getByText('/queue/briefing')).toBeTruthy()
    expect(screen.queryByText('/alerts/HERO-002/defense-case')).toBeNull()
    expect(screen.getByText(/6\/6/i)).toBeTruthy()
    expect(screen.getByText(/Readiness checked 7 backend contract/i)).toBeTruthy()
  })
})
