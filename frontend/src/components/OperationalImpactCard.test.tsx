import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OperationalImpactCard } from './OperationalImpactCard'
import type { OperationalImpact } from '../types'

const impact: OperationalImpact = {
  mode: 'shiftImpact',
  processedAlerts: 31,
  autoClearedAlerts: 13,
  humanReviewAlerts: 18,
  qaSampleAlerts: 3,
  escalationsHeldForSignoff: 12,
  verifierFlagged: 4,
  baselineReviewMinutes: 372,
  assistedReviewMinutes: 141,
  minutesReturned: 231,
  analystHoursReturned: 3.85,
  queueReductionRate: 0.4194,
  reviewFocusMultiplier: 1.72,
  assumptions: ['Baseline review time uses the locked metric artifact: 12 minutes per alert.'],
  controlChecks: ['Escalations remain in human review and cannot be auto-filed.'],
  demoNarrative: 'The operational problem is alert overload: this shift started with 31 alerts.',
  caveat: 'This is a shift-level demo calculation, not a production ROI claim.',
}

describe('OperationalImpactCard', () => {
  it('shows shift workload reduction and controls', () => {
    render(<OperationalImpactCard impact={impact} />)

    expect(screen.getByText(/Operational impact/i)).toBeTruthy()
    expect(screen.getByText(/shift workload/i)).toBeTruthy()
    expect(screen.getByText('13/31')).toBeTruthy()
    expect(screen.getByText('3.85h')).toBeTruthy()
    expect(screen.getByText(/Escalations remain in human review/i)).toBeTruthy()
    expect(screen.getByText(/not a production ROI claim/i)).toBeTruthy()
  })
})
