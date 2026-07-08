import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { QAOutcomeSummaryCard } from './QAOutcomeSummaryCard'
import type { QAOutcomeSummary } from '../types'

const summary: QAOutcomeSummary = {
  reviewed: 2,
  confirmedClears: 1,
  missedSuspicion: 1,
  missRate: 0.5,
  outcomes: [
    {
      alertId: 'HERO-002',
      outcome: 'missedSuspicion',
      reviewer: 'qa-lead',
      note: 'Sample found suspicious activity that should be escalated.',
      reviewedAt: '2026-07-06T10:00:00+08:00',
      source: 'qaSample',
      evidenceEndpoints: ['/alerts/HERO-002/defense-case'],
    },
  ],
}

describe('QAOutcomeSummaryCard', () => {
  it('renders confirmed clears, misses, and reviewer notes', () => {
    render(<QAOutcomeSummaryCard summary={summary} />)

    expect(screen.getByText('QA outcome loop')).toBeTruthy()
    expect(screen.getByText('2 reviewed')).toBeTruthy()
    expect(screen.getByText('missedSuspicion')).toBeTruthy()
    expect(screen.getByText('qa-lead')).toBeTruthy()
    expect(screen.getByText(/Sample found suspicious activity/i)).toBeTruthy()
    expect(screen.getByText('50%')).toBeTruthy()
  })
})
