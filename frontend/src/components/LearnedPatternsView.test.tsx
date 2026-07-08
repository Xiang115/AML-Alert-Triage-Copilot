import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LearnedPatternsView } from './LearnedPatternsView'

const useLearnedPatternsMock = vi.fn()
const useLearningLoopOpportunitiesMock = vi.fn()

vi.mock('../hooks/useLearnedPatterns', () => ({
  useLearnedPatterns: () => useLearnedPatternsMock(),
}))

vi.mock('../hooks/useLearningLoopOpportunities', () => ({
  useLearningLoopOpportunities: () => useLearningLoopOpportunitiesMock(),
}))

describe('LearnedPatternsView', () => {
  beforeEach(() => {
    useLearnedPatternsMock.mockReset()
    useLearningLoopOpportunitiesMock.mockReset()
    useLearningLoopOpportunitiesMock.mockReturnValue({
      scannedAlerts: 31,
      signatureCount: 9,
      teachableSources: 7,
      reusableSources: 1,
      affectedFutureAlerts: 1,
      candidates: [
        {
          sourceAlertId: 'DEMO-CL-01',
          holderName: 'Learned Merchant A',
          signature: 'typ=PT-01|amt=3|dir=mix|drain=False|conc=1|xb=0|cash=0|ntxn=3',
          typology: 'PT-01',
          recommendation: 'dismiss',
          verifierStatus: 'agreed',
          canTeach: true,
          blockedReason: null,
          affectedFutureAlerts: [
            {
              alertId: 'DEMO-CL-02',
              holderName: 'Future Merchant B',
              currentRouting: 'autoCleared',
              confidence: 0.71,
              recommendation: 'dismiss',
            },
          ],
          blockedFutureAlerts: [],
        },
        {
          sourceAlertId: 'SD-00013',
          holderName: 'Escalation Candidate',
          signature: null,
          typology: 'NONE',
          recommendation: 'escalate',
          verifierStatus: 'agreed',
          canTeach: false,
          blockedReason: 'No reusable signature: no matched typology or reusable ledger envelope.',
          affectedFutureAlerts: [],
          blockedFutureAlerts: [],
        },
      ],
    })
  })

  it('shows the suppression firewall controls around learned patterns', () => {
    useLearnedPatternsMock.mockReturnValue([
      {
        signature: 'typ=PT-01|amt=1|dir=mix|drain=True|conc=1|xb=0|cash=0|ntxn=3',
        typology: 'PT-01',
        sourceAlertId: 'SLICEA-001',
        clearedCount: 2,
        clearedAt: '2026-07-06T09:00:00+08:00',
      },
    ])

    render(
      <LearnedPatternsView
        alerts={[
          {
            alertId: 'DEMO-CL-02',
            routing: 'autoCleared',
            account: { holderName: 'Future Merchant B' },
            triage: {
              suppression: {
                status: 'suppressed',
                matchedPatternId: 'typ=PT-01|amt=1|dir=mix|drain=True|conc=1|xb=0|cash=0|ntxn=3',
                signature: 'typ=PT-01|amt=1|dir=mix|drain=True|conc=1|xb=0|cash=0|ntxn=3',
              },
            },
          } as never,
        ]}
      />,
    )

    expect(screen.getByText('Learning loop')).toBeTruthy()
    expect(screen.getByText(/future alerts it now removes from primary review/i)).toBeTruthy()
    expect(screen.getByText('Active suppressions')).toBeTruthy()
    expect(screen.getByText('Suppression firewall')).toBeTruthy()
    expect(screen.getByText('Full-population learning scan')).toBeTruthy()
    expect(screen.getByText('Alerts scanned')).toBeTruthy()
    expect(screen.getByText('31')).toBeTruthy()
    expect(screen.getByText('Teachable dismissals')).toBeTruthy()
    expect(screen.getByText('Reusable sources')).toBeTruthy()
    expect(screen.getByText('DEMO-CL-01')).toBeTruthy()
    expect(screen.getByText(/1 future look-alike removed from primary review/i)).toBeTruthy()
    expect(screen.getByText('Learns only from human dismissals')).toBeTruthy()
    expect(screen.getByText('Acts only inside the firewall')).toBeTruthy()
    expect(screen.getByText('Cannot file or escalate')).toBeTruthy()
    expect(screen.getByText('Revoked by network risk')).toBeTruthy()
    expect(screen.getByText('typ=PT-01|amt=1|dir=mix|drain=True|conc=1|xb=0|cash=0|ntxn=3')).toBeTruthy()
    expect(screen.getByText('SLICEA-001')).toBeTruthy()
    expect(screen.getByText('Future alerts affected')).toBeTruthy()
    expect(screen.getByText('Future look-alikes removed from primary review')).toBeTruthy()
    expect(screen.getAllByText('DEMO-CL-02')).toHaveLength(2)
    expect(screen.getByText('Future Merchant B')).toBeTruthy()
    expect(screen.getByText('SD-00013')).toBeTruthy()
    expect(screen.getByText('No learning effect.')).toBeTruthy()
  })

  it('keeps the firewall visible even before any pattern has been learned', () => {
    useLearnedPatternsMock.mockReturnValue([])

    render(<LearnedPatternsView alerts={[]} />)

    expect(screen.getByText('Suppression firewall')).toBeTruthy()
    expect(screen.getByText('No learning paths yet')).toBeTruthy()
    expect(screen.getByText(/future alerts it affects/i)).toBeTruthy()
  })
})
