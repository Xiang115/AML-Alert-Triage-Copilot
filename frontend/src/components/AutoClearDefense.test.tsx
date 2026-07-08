import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import metricsFixture from '../fixtures/metrics.json'
import type { GovernanceThresholds, Metrics } from '../types'
import { AutoClearDefense } from './AutoClearDefense'

const thresholds: GovernanceThresholds = {
  review: 0.6,
  autoClear: 0.85,
  qaSample: 0.2,
  borderlineMargin: 0.1,
}

describe('AutoClearDefense', () => {
  it('renders the policy, leakage, and QA control together', () => {
    const metrics = metricsFixture as Metrics

    render(<AutoClearDefense metrics={metrics} thresholds={thresholds} qaSampleCount={3} />)

    expect(screen.getByText(/Auto-clear defense/i)).toBeTruthy()
    expect(screen.getByText(/verifier agreed/i)).toBeTruthy()
    expect(screen.getByText(/never auto-escalates/i)).toBeTruthy()
    expect(screen.getByText(/P\(cleared \| true report\)/i)).toBeTruthy()
    expect(screen.getByText(new RegExp('\\((46|42)/150\\)', 'i'))).toBeTruthy()
    expect(screen.getByText(/samples the riskiest clears/i)).toBeTruthy()
  })

  it('does not render when auto-clear metrics are unavailable', () => {
    const { autoClearedShare, autoClearPrecision, ...legacy } = metricsFixture as Metrics
    void autoClearedShare
    void autoClearPrecision

    render(<AutoClearDefense metrics={legacy as Metrics} thresholds={thresholds} qaSampleCount={0} />)

    expect(screen.queryByText(/Auto-clear defense/i)).toBeNull()
  })
})
