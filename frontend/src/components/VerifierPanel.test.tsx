import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VerifierPanel } from './VerifierPanel'
import type { Verifier } from '../types'

// Verifier notes are superseded by anchored claims (ADR-0022/Task 8): the panel renders
// verifier.claims via the shared TracedClaimList, not the free-form `note` prose.
const flagged: Verifier = {
  status: 'flagged',
  agreesWithRecommendation: false,
  claims: [{
    text: 'Could be a small business with high turnover.',
    anchored: false,
    evidence: { transactionIds: [], firedIndicators: [] },
  }],
}

const agreed: Verifier = {
  status: 'agreed',
  agreesWithRecommendation: true,
  claims: [{
    text: 'Evidence clearly meets the distinguishing test.',
    anchored: true,
    evidence: { transactionIds: ['T-1'], firedIndicators: [] },
  }],
}

describe('VerifierPanel', () => {
  it('shows the flagged claim, the alert label, and the manual-review message when flagged', () => {
    render(<VerifierPanel verifier={flagged} />)
    expect(screen.getByText(flagged.claims![0].text)).toBeTruthy()
    expect(screen.getByText(/distinguishing test alert/i)).toBeTruthy()
    expect(screen.getByText(/manual review required/i)).toBeTruthy()
  })

  it('shows the verified state and no review message when agreed', () => {
    render(<VerifierPanel verifier={agreed} />)
    expect(screen.getByText(agreed.claims![0].text)).toBeTruthy()
    expect(screen.getByText(/triage call verified/i)).toBeTruthy()
    expect(screen.queryByText(/manual review required/i)).toBeNull()
  })
})
