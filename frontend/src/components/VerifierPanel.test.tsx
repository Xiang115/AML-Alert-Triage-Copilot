import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VerifierPanel } from './VerifierPanel'
import type { Verifier } from '../types'

const flagged: Verifier = {
  status: 'flagged',
  agreesWithRecommendation: false,
  note: 'Could be a small business with high turnover.',
}

const agreed: Verifier = {
  status: 'agreed',
  agreesWithRecommendation: true,
  note: 'Evidence clearly meets the distinguishing test.',
}

describe('VerifierPanel', () => {
  it('shows the flagged note, the alert label, and the confidence-cap message when flagged', () => {
    render(<VerifierPanel verifier={flagged} />)
    expect(screen.getByText(flagged.note)).toBeTruthy()
    expect(screen.getByText(/distinguishing test alert/i)).toBeTruthy()
    expect(screen.getByText(/capped below threshold/i)).toBeTruthy()
  })

  it('shows the verified state and no cap message when agreed', () => {
    render(<VerifierPanel verifier={agreed} />)
    expect(screen.getByText(agreed.note)).toBeTruthy()
    expect(screen.getByText(/triage call verified/i)).toBeTruthy()
    expect(screen.queryByText(/capped below threshold/i)).toBeNull()
  })
})
