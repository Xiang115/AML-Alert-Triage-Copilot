import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DefenseArtifacts } from './DefenseArtifacts'
import type { ReadinessSummary } from '../types'

const readiness: ReadinessSummary = {
  status: 'pass',
  checkedAt: '2026-07-06T10:00:00+08:00',
  checks: [
    { name: 'contract /finals/evidence-bundle', endpoint: '/finals/evidence-bundle', ok: true, detail: 'ok' },
    { name: 'contract /health', endpoint: '/health', ok: true, detail: 'ok' },
    { name: 'contract /metrics', endpoint: '/metrics', ok: true, detail: 'ok' },
    { name: 'contract /governance', endpoint: '/governance', ok: true, detail: 'ok' },
    { name: 'contract /security/access-control', endpoint: '/security/access-control', ok: true, detail: 'ok' },
    { name: 'contract /governance/change-requests', endpoint: '/governance/change-requests', ok: true, detail: 'ok' },
    { name: 'contract /qa/outcomes', endpoint: '/qa/outcomes', ok: true, detail: 'ok' },
    { name: 'contract /queue/briefing', endpoint: '/queue/briefing', ok: true, detail: 'ok' },
    { name: 'contract /alerts/HERO-002/defense-case', endpoint: '/alerts/HERO-002/defense-case', ok: true, detail: 'ok' },
    { name: 'contract /alerts/HERO-002/case-handoff', endpoint: '/alerts/HERO-002/case-handoff', ok: true, detail: 'ok' },
    { name: 'contract /alerts/HERO-002/decision-trace', endpoint: '/alerts/HERO-002/decision-trace', ok: true, detail: 'ok' },
    { name: 'contract /alerts/HERO-002/copilot-runs/precomputed-current/ledger', endpoint: '/alerts/HERO-002/copilot-runs/precomputed-current/ledger', ok: true, detail: 'ok' },
    { name: 'contract /operations/impact', endpoint: '/operations/impact', ok: true, detail: 'ok' },
    { name: 'contract /architecture/technical', endpoint: '/architecture/technical', ok: true, detail: 'ok' },
    { name: 'contract /integration/contract', endpoint: '/integration/contract', ok: true, detail: 'ok' },
    { name: 'contract /production/trust-plan', endpoint: '/production/trust-plan', ok: true, detail: 'ok' },
    { name: 'contract /pilot/adoption-plan', endpoint: '/pilot/adoption-plan', ok: true, detail: 'ok' },
    { name: 'contract /innovation/differentiation', endpoint: '/innovation/differentiation', ok: true, detail: 'ok' },
    { name: 'contract /finals/demo-script', endpoint: '/finals/demo-script', ok: true, detail: 'ok' },
    { name: 'contract /finals/qna-defense', endpoint: '/finals/qna-defense', ok: true, detail: 'ok' },
    { name: 'contract /governance/validation-dossier', endpoint: '/governance/validation-dossier', ok: true, detail: 'ok' },
  ],
}

describe('DefenseArtifacts', () => {
  it('lists only the essential system-level contracts behind finals claims', () => {
    render(<DefenseArtifacts readiness={readiness} />)

    expect(screen.getByText(/Defense artifacts/i)).toBeTruthy()
    expect(screen.getByText('/finals/evidence-bundle')).toBeTruthy()
    expect(screen.getByText('/metrics')).toBeTruthy()
    expect(screen.getByText('/queue/briefing')).toBeTruthy()
    expect(screen.getByText('/operations/impact')).toBeTruthy()
    expect(screen.getByText('/architecture/technical')).toBeTruthy()
    expect(screen.getByText('/governance/validation-dossier')).toBeTruthy()
    expect(screen.getByText('/integration/contract')).toBeTruthy()
    expect(screen.getByText('/pilot/adoption-plan')).toBeTruthy()
    expect(screen.getByText('/innovation/differentiation')).toBeTruthy()
    expect(screen.getByText('/finals/qna-defense')).toBeTruthy()

    expect(screen.queryByText('/alerts/HERO-002/defense-case')).toBeNull()
    expect(screen.queryByText('/alerts/HERO-002/case-handoff')).toBeNull()
    expect(screen.queryByText('/alerts/HERO-002/decision-trace')).toBeNull()
  })

  it('states what each essential artifact proves', () => {
    render(<DefenseArtifacts readiness={readiness} />)

    expect(screen.getByText(/Single packet tying the finals claims/i)).toBeTruthy()
    expect(screen.getByText(/Held-out performance, baseline comparison/i)).toBeTruthy()
    expect(screen.getByText(/The Queue Agent produces a real worklist/i)).toBeTruthy()
    expect(screen.getByText(/Workflow pain and measurable shift-level workload/i)).toBeTruthy()
    expect(screen.getByText(/End-to-end system shape/i)).toBeTruthy()
    expect(screen.getByText(/Auto-clear leakage, shadow-only state/i)).toBeTruthy()
    expect(screen.getByText(/Required bank fields, outbound artifacts/i)).toBeTruthy()
    expect(screen.getByText(/Commercial rollout path/i)).toBeTruthy()
    expect(screen.getByText(/Why this is not just a chatbot/i)).toBeTruthy()
    expect(screen.getByText(/Likely judge objections mapped to answers/i)).toBeTruthy()
  })

  it('shows readiness only for the essential rows', () => {
    render(<DefenseArtifacts readiness={readiness} />)

    expect(screen.getByText(/readiness passed/i)).toBeTruthy()
    expect(screen.getAllByText('pass')).toHaveLength(10)
    expect(screen.getByText(/Backend readiness checked 21 contract/i)).toBeTruthy()
  })
})
