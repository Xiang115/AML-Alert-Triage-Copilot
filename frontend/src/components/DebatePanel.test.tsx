import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DebatePanel } from './DebatePanel'
import type { Debate } from '../types'

const holds: Debate = {
  challenge: {
    counterHypothesis: 'A legitimate merchant consolidating customer payments.',
    distinguishingTestAssessment: 'The balance is retained, so the fan-in test is not satisfied.',
  },
  rebuttal: { argument: 'The senders are unrelated individuals.', conceded: false },
  reverdict: { outcome: 'holds', dispositionChanged: false, note: 'The flag holds — refer to a human analyst.' },
}

const conceded: Debate = {
  challenge: { counterHypothesis: 'An active pass-through.', distinguishingTestAssessment: 'Same-day sweep.' },
  rebuttal: { argument: 'On reflection the sweep fits the typology.', conceded: true },
  reverdict: { outcome: 'conceded', dispositionChanged: true, note: 'Triage conceded; disposition changed to escalate.' },
}

describe('DebatePanel', () => {
  it('renders all three turns and the holds outcome', () => {
    render(<DebatePanel debate={holds} />)
    expect(screen.getByText(holds.challenge.counterHypothesis)).toBeTruthy()
    expect(screen.getByText(holds.rebuttal.argument)).toBeTruthy()
    expect(screen.getByText(holds.reverdict.note)).toBeTruthy()
    expect(screen.getByText('Flag holds — human review')).toBeTruthy()  // the outcome badge
  })

  it('marks a conceded rebuttal and a disposition change', () => {
    render(<DebatePanel debate={conceded} />)
    expect(screen.getByText(/triage rebuttal — conceded/i)).toBeTruthy()
    expect(screen.getByText('Disposition changed')).toBeTruthy()  // the outcome badge
  })
})
