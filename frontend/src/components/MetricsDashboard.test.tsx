import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MetricsDashboard } from './MetricsDashboard'
import metricsFixture from '../fixtures/metrics.json'
import type { Metrics } from '../types'

const M = metricsFixture as Metrics

// The autonomy numbers (ADR-0010) render with the honest recall-ceiling caveat, not a lone figure.
describe('MetricsDashboard — autonomous queue agent', () => {
  it('shows the auto-clear numbers paired with the honest caveat', () => {
    render(<MetricsDashboard metrics={M} />)
    expect(screen.getByText(/Queue auto-cleared/i)).toBeTruthy()
    expect(screen.getByText(/Auto-clear precision/i)).toBeTruthy()
    expect(screen.getByText(`${(M.autoClearedShare! * 100).toFixed(0)}%`)).toBeTruthy() // autoClearedShare
    expect(screen.getByText(/Mule-Network roadmap/i)).toBeTruthy() // the honest answer to the miss rate
  })

  it('omits the autonomy card when the metrics predate the Queue Agent', () => {
    const { autoClearedShare, autoClearPrecision, ...legacy } = M
    void autoClearedShare
    void autoClearPrecision
    render(<MetricsDashboard metrics={legacy as Metrics} />)
    expect(screen.queryByText(/Queue auto-cleared/i)).toBeNull()
  })
})

// The SAML-D measurement (ADR-0012): recall-led headline, per-typology bars, confusion matrix.
describe('MetricsDashboard — SAML-D held-out evaluation', () => {
  it('leads with catch-rate (recall), not accuracy', () => {
    render(<MetricsDashboard metrics={M} />)
    expect(screen.getAllByText(/Catch rate \(recall\)/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(`${(M.recall * 100).toFixed(0)}%`).length).toBeGreaterThan(0)
  })

  it('explains the always-dismiss baseline without implying it is production-base-rate derived', () => {
    render(<MetricsDashboard metrics={M} />)
    expect(screen.getByText(/always dismissing this held-out slice/i)).toBeTruthy()
    expect(screen.getByText(/baseline is simply the benign share/i)).toBeTruthy()
    expect(screen.getAllByText(/catches zero reportable cases/i).length).toBeGreaterThan(0)
  })

  it('renders per-typology recall bars with the fan-in detector', () => {
    render(<MetricsDashboard metrics={M} />)
    expect(screen.getByText(/Per-typology catch rate/i)).toBeTruthy()
    expect(screen.getAllByText(/Fan-in/i).length).toBeGreaterThan(0)
    const fi = M.perTypologyRecall!['FI-01']
    expect(screen.getAllByText(new RegExp(`\\(${fi.caught}/${fi.total}\\)`)).length).toBeGreaterThan(0)
  })

  it('renders the confusion matrix with the ground-truth axes', () => {
    render(<MetricsDashboard metrics={M} />)
    expect(screen.getByText(/Confusion matrix/i)).toBeTruthy()
    expect(screen.getByText(/missed report/i)).toBeTruthy()
    expect(screen.getByText(`${M.confusionMatrix.tp}`)).toBeTruthy()
  })

  it('keeps the honest coverage note (KYC-01 residual)', () => {
    render(<MetricsDashboard metrics={M} />)
    expect(screen.getAllByText(/KYC-01 is the honest residual/i).length).toBeGreaterThan(0)
  })
})
