import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TechnicalArchitectureCard } from './TechnicalArchitectureCard'
import type { TechnicalArchitecture } from '../types'

const architecture: TechnicalArchitecture = {
  mode: 'technicalArchitecture',
  thesis: 'VerdictAML is an end-to-end AML triage workflow.',
  components: [
    {
      id: 'bank-monitoring',
      name: 'Existing bank monitoring engine',
      layer: 'bank',
      responsibility: 'Emits alert data.',
      proofEndpoints: ['/integration/contract'],
    },
    {
      id: 'queue-agent',
      name: 'Queue Agent',
      layer: 'agent',
      responsibility: 'Builds the overnight queue split.',
      proofEndpoints: ['/queue/briefing', '/operations/impact'],
    },
  ],
  flows: [
    {
      source: 'bank-monitoring',
      target: 'queue-agent',
      payload: 'Alert metadata plus ledger window.',
      control: 'Input schema validation rejects malformed alerts.',
    },
  ],
  dataHandling: ['Pilot deployment starts read-only on historical alerts.'],
  aiExecution: ['Verifier agent challenges the first-pass decision.'],
  reliabilityControls: ['Readiness validates judge-facing contracts.', 'STR filing is human-gated.'],
  demoPath: ['Open Technical Architecture.', 'Open Readiness Summary / Evidence Bundle.'],
  caveat: 'Production deployment requires bank data residency and model-risk signoff.',
}

describe('TechnicalArchitectureCard', () => {
  it('shows components, flows, controls, and proof endpoints', () => {
    render(<TechnicalArchitectureCard architecture={architecture} />)

    expect(screen.getAllByText(/Technical architecture/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/end-to-end flow/i)).toBeTruthy()
    expect(screen.getByText(/Existing bank monitoring engine/i)).toBeTruthy()
    expect(screen.getByText(/Queue Agent/i)).toBeTruthy()
    expect(screen.getByText('/operations/impact')).toBeTruthy()
    expect(screen.getByText(/bank-monitoring -> queue-agent/i)).toBeTruthy()
    expect(screen.getByText(/Readiness validates/i)).toBeTruthy()
    expect(screen.getByText(/Production deployment requires/i)).toBeTruthy()
  })
})
