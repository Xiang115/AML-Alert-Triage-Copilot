import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FinalsQADefense } from './FinalsQADefense'
import type { FinalsQADefensePacket } from '../types'

const packet: FinalsQADefensePacket = {
  mode: 'judgeDefense',
  primaryPosition: 'VerdictAML is built to make AML triage defensible.',
  answers: [
    {
      objection: 'Auto-clear safety: what if the system clears a suspicious case?',
      shortAnswer: 'Auto-clear is threshold-gated and shadow-only until bank replay.',
      evidenceEndpoints: ['/governance/validation-dossier', '/alerts/HERO-002/defense-case'],
      demoAction: 'Open the validation dossier and defense case.',
      trapToAvoid: 'Do not say the clear rate is production-safe.',
    },
    {
      objection: 'Innovation: why not just another LLM wrapper?',
      shortAnswer: 'The differentiator is the control system around the model.',
      evidenceEndpoints: ['/innovation/differentiation'],
      demoAction: 'Open innovation differentiation.',
      trapToAvoid: 'Do not claim novelty because it uses an LLM.',
    },
  ],
  closingLine: 'Expose evidence, controls, limits, and gates.',
}

describe('FinalsQADefense', () => {
  it('maps judge objections to evidence-backed answers', () => {
    render(<FinalsQADefense packet={packet} />)

    expect(screen.getByText(/Finals Q&A defense/i)).toBeTruthy()
    expect(screen.getByText(/evidence answers/i)).toBeTruthy()
    expect(screen.getByText(/Auto-clear safety/i)).toBeTruthy()
    expect(screen.getByText(/threshold-gated and shadow-only/i)).toBeTruthy()
    expect(screen.getByText('/governance/validation-dossier')).toBeTruthy()
    expect(screen.getByText(/Open the validation dossier/i)).toBeTruthy()
  })

  it('shows traps to avoid and the closing line', () => {
    render(<FinalsQADefense packet={packet} />)

    expect(screen.getByText(/Do not say the clear rate is production-safe/i)).toBeTruthy()
    expect(screen.getByText(/Do not claim novelty because it uses an LLM/i)).toBeTruthy()
    expect(screen.getByText(/Expose evidence, controls, limits/i)).toBeTruthy()
  })
})
