import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ShiftBriefingBanner } from './ShiftBriefing'
import type { ShiftBriefing } from '../types'

const briefing: ShiftBriefing = {
  generatedAt: '2026-07-06T09:00:00+08:00',
  processed: 31,
  autoCleared: 6,
  needsReview: 25,
  escalations: 18,
  flagged: 6,
  blockedReasons: [
    {
      code: 'escalation',
      label: 'Escalations to sign',
      count: 18,
      explanation: 'Escalation is consequential and can never be auto-cleared or auto-filed.',
    },
    {
      code: 'adversarialDebate',
      label: 'Adversarial debate',
      count: 1,
      explanation: 'The agents contested the call; contested alerts are firewalled from auto-clear.',
    },
    {
      code: 'lowConfidenceDismiss',
      label: 'Low-confidence dismissals',
      count: 6,
      explanation: 'The alert was a dismiss, but confidence did not meet the auto-clear bar.',
    },
  ],
  nextActions: [
    {
      priority: 1,
      label: 'Sign escalation-ready cases',
      lane: 'needsReview',
      count: 18,
      rationale: 'Consequential cases stay human-gated; clear these first for filing SLA and compliance review.',
    },
    {
      priority: 2,
      label: 'Review low-confidence dismissals',
      lane: 'needsReview',
      count: 6,
      rationale: 'These are benign-looking alerts that failed the auto-clear confidence bar.',
    },
    {
      priority: 3,
      label: 'Spot-check cleared lane',
      lane: 'qaSample',
      count: 6,
      rationale: 'The agent removed benign noise, but sampled clears remain inspectable for leakage control.',
    },
  ],
  summary: 'Processed 31 alerts overnight. Auto-cleared 6 high-confidence benign dismissals; 25 need your review.',
}

describe('ShiftBriefingBanner', () => {
  it('shows the operational queue split and blocked auto-clear reasons', () => {
    render(
      <ShiftBriefingBanner
        briefing={briefing}
        lane="needsReview"
        onLaneChange={() => {}}
        qaSampleCount={2}
        learningImpactCount={0}
        metrics={null}
        thresholds={null}
      />,
    )

    expect(screen.getByText('Queue Agent · overnight run')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Auto-cleared 6/i })).toBeTruthy()
    expect(screen.getByText(/Blocked from auto-clear/i)).toBeTruthy()
    expect(screen.getByText(/Learning loop impact/i)).toBeTruthy()
    expect(screen.getByText(/Future look-alikes removed from primary review/i)).toBeTruthy()
    expect(screen.getByText(/Next operating moves/i)).toBeTruthy()
    expect(screen.getByText('Sign escalation-ready cases')).toBeTruthy()
    expect(screen.getByText('Spot-check cleared lane')).toBeTruthy()
    expect(screen.getByText('25/25')).toBeTruthy()
    expect(screen.getByText('Escalations to sign')).toBeTruthy()
    expect(screen.getByText('Adversarial debate')).toBeTruthy()
    expect(screen.getByText('Low-confidence dismissals')).toBeTruthy()
  })

  it('keeps the lane chips interactive', () => {
    const onLaneChange = vi.fn()
    render(
      <ShiftBriefingBanner
        briefing={briefing}
        lane="needsReview"
        onLaneChange={onLaneChange}
        qaSampleCount={2}
        learningImpactCount={2}
        metrics={null}
        thresholds={null}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Auto-cleared 6/i }))
    expect(onLaneChange).toHaveBeenCalledWith('autoCleared')

    fireEvent.click(screen.getByRole('button', { name: /Spot-check cleared lane/i }))
    expect(onLaneChange).toHaveBeenCalledWith('qaSample')

    fireEvent.click(screen.getByRole('button', { name: /Inspect learned auto-clears/i }))
    expect(onLaneChange).toHaveBeenCalledWith('autoCleared')
  })
})
