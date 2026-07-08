import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { InnovationDifferentiation } from './InnovationDifferentiation'
import type { InnovationDifferentiation as InnovationDifferentiationData } from '../types'

const packet: InnovationDifferentiationData = {
  mode: 'evidenceBackedDifferentiation',
  thesis: 'VerdictAML is differentiated by controls around AML triage.',
  capabilities: [
    {
      name: 'Adversarial verifier and debate',
      genericAlternative: 'Single-pass LLM classification.',
      verdictamlImplementation: 'Verifier challenges the first triage answer.',
      proofEndpoints: ['/alerts/HERO-002/defense-case'],
      defenseValue: 'Shows why the call survived challenge.',
      limitation: 'Human judgment still owns consequential decisions.',
    },
    {
      name: 'Human-gated goAML export',
      genericAlternative: 'Generate STR prose.',
      verdictamlImplementation: 'goAML is blocked until sign-off and evidence anchoring pass.',
      proofEndpoints: ['/integration/contract'],
      defenseValue: 'Makes filing controls auditable.',
      limitation: 'Real submission depends on bank rails.',
    },
  ],
  nonClaims: ['Not novelty by LLM usage alone.', 'Not claiming autonomous STR filing.'],
}

describe('InnovationDifferentiation', () => {
  it('shows built differentiators against generic alternatives', () => {
    render(<InnovationDifferentiation packet={packet} />)

    expect(screen.getByText(/Innovation differentiation/i)).toBeTruthy()
    expect(screen.getByText(/evidence-backed/i)).toBeTruthy()
    expect(screen.getByText(/Single-pass LLM classification/i)).toBeTruthy()
    expect(screen.getByText(/Verifier challenges/i)).toBeTruthy()
    expect(screen.getByText('/alerts/HERO-002/defense-case')).toBeTruthy()
  })

  it('states limitations and non-claims', () => {
    render(<InnovationDifferentiation packet={packet} />)

    expect(screen.getByText(/Human judgment still owns/i)).toBeTruthy()
    expect(screen.getByText(/Not novelty by LLM usage alone/i)).toBeTruthy()
    expect(screen.getByText(/Not claiming autonomous STR filing/i)).toBeTruthy()
  })
})
