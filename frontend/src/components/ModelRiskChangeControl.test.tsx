import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ModelRiskChangeControl } from './ModelRiskChangeControl'
import type { GovernanceChangeRequestList } from '../types'

const data: GovernanceChangeRequestList = {
  mode: 'modelRiskChangeControl',
  pending: 1,
  approved: 0,
  blockedReason: 'Runtime config is immutable from the API.',
  changes: [
    {
      changeId: 'chg-threshold-auto-clear-hardening',
      type: 'thresholdChange',
      status: 'proposed',
      requestedBy: 'model-risk',
      requestedAt: '2026-07-06T10:00:00+08:00',
      currentValue: { autoClear: 0.85 },
      proposedValue: { autoClear: 0.9 },
      rationale: 'Raise the auto-clear bar until QA outcomes prove leakage remains inside tolerance.',
      evidence: ['/governance/validation-dossier', '/qa/outcomes'],
      requiredApprovals: ['compliance', 'modelRisk'],
      approvals: [],
      rollbackPlan: 'Restore previous thresholds and replay the shadow sample.',
      nonClaims: ['This proposal does not mutate runtime thresholds.'],
    },
  ],
}

describe('ModelRiskChangeControl', () => {
  it('renders pending governance changes with approvals and rollback', () => {
    render(<ModelRiskChangeControl data={data} />)

    expect(screen.getByText('Model-risk change control')).toBeTruthy()
    expect(screen.getByText('1 pending')).toBeTruthy()
    expect(screen.getByText('chg-threshold-auto-clear-hardening')).toBeTruthy()
    expect(screen.getByText('compliance approval')).toBeTruthy()
    expect(screen.getByText(/Restore previous thresholds/i)).toBeTruthy()
    expect(screen.getByText(/\/qa\/outcomes/i)).toBeTruthy()
  })
})
