import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MetricsDashboard } from './MetricsDashboard'
import metricsFixture from '../fixtures/metrics.json'
import type { Metrics } from '../types'

// The autonomy numbers (ADR-0010) render with the honest recall-ceiling caveat, not a lone 90%.
describe('MetricsDashboard — autonomous queue agent', () => {
  it('shows the auto-clear numbers paired with the honest caveat', () => {
    render(<MetricsDashboard metrics={metricsFixture as Metrics} />)
    expect(screen.getByText(/Queue auto-cleared/i)).toBeTruthy()
    expect(screen.getByText(/Auto-clear precision/i)).toBeTruthy()
    expect(screen.getByText('90%')).toBeTruthy() // autoClearedShare
    expect(screen.getByText(/Mule-Network roadmap/i)).toBeTruthy() // the honest answer to the miss rate
  })

  it('omits the autonomy card when the metrics predate the Queue Agent', () => {
    const { autoClearedShare, autoClearPrecision, ...legacy } = metricsFixture as Metrics
    void autoClearedShare
    void autoClearPrecision
    render(<MetricsDashboard metrics={legacy as Metrics} />)
    expect(screen.queryByText(/Queue auto-cleared/i)).toBeNull()
  })
})
