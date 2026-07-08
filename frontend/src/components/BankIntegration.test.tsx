import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BankIntegration } from './BankIntegration'
import type { BankIntegrationContract } from '../types'

const contract: BankIntegrationContract = {
  mode: 'shadowFirst',
  inboundSystems: ['SAS', 'Actimize', 'Mantas', 'bank rule engine'],
  workflow: [
    {
      title: 'Existing monitoring',
      body: 'SAS / Actimize / Mantas / bank rule engine emits alert id, account, trigger, risk score, and transaction window.',
    },
    {
      title: 'Case-management worklist',
      body: 'needsReview goes to analyst queue; autoCleared remains inspectable, QA-sampled, and logged.',
    },
    {
      title: 'goAML filing seam',
      body: 'Approved STR exports as schema-valid goAML XML; filing returns FIU acknowledgement and audit event.',
    },
  ],
  minimumRequiredFields: [
    {
      name: 'transaction id, timestamp, direction, amount, currency',
      required: true,
      source: 'ledger / alert transaction window',
      reason: 'Grounds typology indicators, cited transactions, and STR amounts.',
    },
  ],
  optionalEnrichments: [
    {
      name: 'confirmed STR / no-STR outcome',
      required: false,
      source: 'case-management disposition history',
      reason: 'Needed for bank-specific validation, threshold approval, and override analysis.',
    },
  ],
  outboundArtifacts: ['Defense case JSON', 'goAML XML export'],
  productionGates: ['Start read-only on historical alerts.', 'QA sampling and audit remain always on.'],
  nonGoals: ['Does not replace the source transaction-monitoring detector.', 'Does not auto-file STRs.'],
}

describe('BankIntegration', () => {
  it('shows where VerdictAML fits in the bank workflow', () => {
    render(<BankIntegration contract={contract} />)

    expect(screen.getByText(/Bank integration path/i)).toBeTruthy()
    expect(screen.getAllByText(/SAS \/ Actimize \/ Mantas/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Case-management worklist/i)).toBeTruthy()
    expect(screen.getByText(/goAML filing seam/i)).toBeTruthy()
  })

  it('states data access and production validation gates', () => {
    render(<BankIntegration contract={contract} />)

    expect(screen.getByText(/Minimum data access/i)).toBeTruthy()
    expect(screen.getByText(/transaction id, timestamp, direction, amount, currency/i)).toBeTruthy()
    expect(screen.getByText(/confirmed STR \/ no-STR outcome/i)).toBeTruthy()
    expect(screen.getByText(/Start read-only on historical alerts/i)).toBeTruthy()
    expect(screen.getByText(/QA sampling and audit remain always on/i)).toBeTruthy()
    expect(screen.getByText(/Does not auto-file STRs/i)).toBeTruthy()
  })
})
