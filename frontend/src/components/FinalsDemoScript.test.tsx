import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FinalsDemoScript } from './FinalsDemoScript'
import type { FinalsDemoScript as FinalsDemoScriptData } from '../types'

const script: FinalsDemoScriptData = {
  mode: 'finalsDemo',
  openingLine: 'The operational problem is AML queue overload.',
  totalMinutes: 7,
  steps: [
    {
      title: 'Start with operational pain',
      timeboxMinutes: 1,
      objective: 'Show impact.',
      route: '#/governance',
      action: 'Open Operational Impact.',
      evidenceEndpoints: ['/operations/impact'],
      judgeTakeaway: 'Concrete workflow value.',
      fallback: 'Open /operations/impact directly.',
    },
    {
      title: 'Show architecture',
      timeboxMinutes: 1,
      objective: 'Show end-to-end flow.',
      route: '#/governance',
      action: 'Open Technical Architecture.',
      evidenceEndpoints: ['/architecture/technical'],
      judgeTakeaway: 'Typed architecture.',
      fallback: 'Open /architecture/technical directly.',
    },
  ],
  fallbackMoves: ['If a panel is slow, open the matching endpoint directly and show readiness passes.'],
  closingLine: 'VerdictAML exposes evidence, controls, and limits.',
  nonClaims: ['Do not claim autonomous STR filing.'],
}

describe('FinalsDemoScript', () => {
  it('shows timed demo steps, evidence endpoints, fallbacks, and non-claims', () => {
    render(<FinalsDemoScript script={script} />)

    expect(screen.getByText(/Finals demo path/i)).toBeTruthy()
    expect(screen.getByText(/7 min run/i)).toBeTruthy()
    expect(screen.getByText(/Start with operational pain/i)).toBeTruthy()
    expect(screen.getByText('/operations/impact')).toBeTruthy()
    expect(screen.getByText(/Concrete workflow value/i)).toBeTruthy()
    expect(screen.getByText(/show readiness passes/i)).toBeTruthy()
    expect(screen.getByText(/Do not claim autonomous STR filing/i)).toBeTruthy()
  })
})
