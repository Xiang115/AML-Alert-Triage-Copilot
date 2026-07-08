import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProductionTrustPlanCard } from './ProductionTrustPlanCard'
import type { ProductionTrustPlan } from '../types'

const plan: ProductionTrustPlan = {
  mode: 'productionTrustPlan',
  position: 'VerdictAML does not ask a bank to trust demo auto-clear.',
  targetSystems: ['SAS AML / Actimize / Mantas', 'Case-management system', 'FIU/goAML filing rail'],
  minimumDataAccess: ['Transaction id, amount, and running balance.', 'Historical analyst disposition and confirmed STR/no-STR outcome.'],
  governanceControls: ['Verifier agreement, QA sampling, leakage measurement, override review, and screening gates.'],
  validationGates: ['Historical replay.', 'Shadow pilot.', 'Model-risk, compliance, security, and rollback sign-off.'],
  items: [
    {
      area: 'falsePositiveGovernance',
      requirement: 'Govern false positives without creating false clears.',
      implementation: 'Suppression only applies when controls agree.',
      evidenceEndpoints: ['/governance/validation-dossier', '/queue/briefing'],
      productionGate: 'Suppression starts shadow-only.',
    },
  ],
  judgeResponse: 'A bank should not trust our demo to auto-clear production alerts.',
  nonClaims: ['Synthetic metrics are not production performance.', 'No autonomous STR filing.'],
}

describe('ProductionTrustPlanCard', () => {
  it('shows bank systems, data access, governance, validation, and non-claims', () => {
    render(<ProductionTrustPlanCard plan={plan} />)

    expect(screen.getByText(/Production trust plan/i)).toBeTruthy()
    expect(screen.getByText(/bank-trust gates/i)).toBeTruthy()
    expect(screen.getByText(/does not ask a bank to trust demo auto-clear/i)).toBeTruthy()
    expect(screen.getByText(/SAS AML \/ Actimize \/ Mantas/i)).toBeTruthy()
    expect(screen.getByText(/Transaction id, amount, and running balance/i)).toBeTruthy()
    expect(screen.getByText(/Verifier agreement, QA sampling, leakage measurement/i)).toBeTruthy()
    expect(screen.getByText(/Shadow pilot/i)).toBeTruthy()
    expect(screen.getByText(/Govern false positives without creating false clears/i)).toBeTruthy()
    expect(screen.getByText('/governance/validation-dossier')).toBeTruthy()
    expect(screen.getByText(/No autonomous STR filing/i)).toBeTruthy()
  })
})
