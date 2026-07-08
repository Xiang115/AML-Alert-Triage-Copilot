import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CoachingPanel } from './CoachingPanel'
import type { TriageResult } from '../types'

// CoachingPanel only reads triage.matchedTypology.code, so a partial triage is enough.
function triageWith(code: string): TriageResult {
  return { matchedTypology: { code, name: 'x', source: 'y' } } as TriageResult
}

describe('CoachingPanel', () => {
  it('renders the playbook for a matched typology (PT-01)', () => {
    render(<CoachingPanel triage={triageWith('PT-01')} />)
    expect(screen.getByText(/analyst playbook/i)).toBeTruthy()
    expect(screen.getByText(/distinguishing test:/i)).toBeTruthy()
    expect(screen.getByText(/benign look-alike:/i)).toBeTruthy()
    expect(screen.getByText(/what to check/i)).toBeTruthy()
    expect(screen.getByText(/regulator red flags/i)).toBeTruthy()   // the grounded section
    expect(screen.getByText(/BNM AML\/CFT\/CPF PD Feb 2024, App\. 4a #16/)).toBeTruthy()  // real source tag
    expect(screen.getByText(/^Policy:/)).toBeTruthy()  // the verified citation
  })

  it('renders nothing when no card matches (a NO_MATCH dismiss)', () => {
    const { container } = render(<CoachingPanel triage={triageWith('NO_MATCH')} />)
    expect(container.firstChild).toBeNull()
  })
})
