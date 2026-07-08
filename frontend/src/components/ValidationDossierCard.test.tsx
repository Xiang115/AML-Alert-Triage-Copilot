import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ValidationDossierCard } from './ValidationDossierCard'
import type { ValidationDossier } from '../types'

const dossier: ValidationDossier = {
  validatedAt: '2026-07-05T12:00:00+08:00',
  model: 'deepseek-v4-pro',
  dataset: 'SAML-D held-out report-enriched slice',
  n: 250,
  accuracyVsLabels: 0.69,
  baselineAccuracy: 0.4,
  baselineExplanation: 'Always-dismiss baseline on this held-out slice: it equals the benign share and catches zero reportable cases.',
  recall: 0.72,
  precision: 0.75,
  specificity: 0.66,
  confusionMatrix: { tp: 108, fp: 36, fn: 42, tn: 64 },
  autoClearedShare: 0.42,
  autoClearPrecision: 0.96,
  autoClearedReports: 1,
  totalReports: 150,
  autoClearLeakageRate: 0.0067,
  thresholds: { review: 0.6, autoClear: 0.85, qaSample: 0.2, borderlineMargin: 0.1 },
  measuredTypologies: ['PT-01', 'PT-02'],
  roadmapTypologies: ['PT-03'],
  productionState: 'shadowOnly',
  releaseGates: [
    'Historical replay against known analyst decisions and confirmed STR outcomes.',
    'Compliance-approved auto-clear threshold and documented leakage tolerance.',
  ],
  prohibitedActions: ['No auto-filing to goAML.', 'No clearing sanctions/PEP screening hits.'],
}

describe('ValidationDossierCard', () => {
  it('surfaces the measured validation numbers and baseline meaning', () => {
    render(<ValidationDossierCard dossier={dossier} />)

    expect(screen.getByText(/Validation dossier/i)).toBeTruthy()
    expect(screen.getByText(/shadow only/i)).toBeTruthy()
    expect(screen.getByText(/Recall/i)).toBeTruthy()
    expect(screen.getByText(/72%/i)).toBeTruthy()
    expect(screen.getByText(/Always-dismiss baseline/i)).toBeTruthy()
    expect(screen.getByText(/catches zero reportable cases/i)).toBeTruthy()
  })

  it('states release gates and prohibited production actions', () => {
    render(<ValidationDossierCard dossier={dossier} />)

    expect(screen.getByText(/Release gates/i)).toBeTruthy()
    expect(screen.getByText(/known analyst decisions/i)).toBeTruthy()
    expect(screen.getByText(/Still prohibited/i)).toBeTruthy()
    expect(screen.getByText(/No auto-filing to goAML/i)).toBeTruthy()
    expect(screen.getByText(/No clearing sanctions\/PEP screening hits/i)).toBeTruthy()
  })
})
