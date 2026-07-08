import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OverrideFeedback } from './OverrideFeedback'

describe('OverrideFeedback', () => {
  it('shows overrides as a governance feedback loop', () => {
    render(<OverrideFeedback override={{ decisions: 10, overrides: 3, overrideRate: 0.3 }} />)

    expect(screen.getByText(/Override feedback loop/i)).toBeTruthy()
    expect(screen.getByText(/live calibration signal/i)).toBeTruthy()
    expect(screen.getByText(/AI call, human disposition, verifier status, confidence, and analyst reason/i)).toBeTruthy()
    expect(screen.getByText(/Typology cards, thresholds, and QA sampling rules/i)).toBeTruthy()
    expect(screen.getAllByText('30%').length).toBeGreaterThan(0)
  })

  it('handles sessions with no decisions yet', () => {
    render(<OverrideFeedback override={{ decisions: 0, overrides: 0, overrideRate: null }} />)

    expect(screen.getAllByText(/no decisions yet/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText('0')).toHaveLength(2)
  })
})
