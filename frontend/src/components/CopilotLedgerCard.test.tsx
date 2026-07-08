import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { CopilotRunLedger, CopilotRunSummary } from '../types'
import { CopilotLedgerCard } from './CopilotLedgerCard'

const ledger: CopilotRunLedger = {
  runId: 'run_123',
  alertId: 'HERO-002',
  mode: 'live',
  provider: 'deepseek',
  model: 'deepseek-v4-pro',
  status: 'completed',
  startedAt: '2026-07-07T12:00:00+08:00',
  completedAt: '2026-07-07T12:00:02+08:00',
  latencyMs: 2000,
  promptVersion: 'captured-runtime-envelope',
  inputSnapshot: { alertId: 'HERO-002' },
  retrieval: { candidateCount: 5 },
  llmCalls: [
    {
      stage: 'triageAgent',
      templateId: 'triage-agent-v1',
      model: 'deepseek-v4-pro',
      responseModel: 'TriageOutput',
      attempt: 1,
      messages: [
        { role: 'system', content: 'system prompt', contentHash: 'sha256:abc', redactionLevel: 'piiRedacted' },
        { role: 'user', content: 'user prompt', contentHash: 'sha256:def', redactionLevel: 'piiRedacted' },
      ],
      rawResponse: '{"recommendation":"escalate"}',
      rawResponseHash: 'sha256:1234567890abcdef',
      schemaValid: true,
      validationError: null,
    },
    {
      stage: 'verifier',
      templateId: 'verifier-v1',
      model: 'deepseek-v4-flash',
      responseModel: 'Verifier',
      attempt: 1,
      messages: [
        { role: 'system', content: 'verifier prompt', contentHash: 'sha256:ghi', redactionLevel: 'piiRedacted' },
      ],
      rawResponse: '{"agreesWithRecommendation":true}',
      rawResponseHash: 'sha256:abcdef1234567890',
      schemaValid: true,
      validationError: null,
    },
  ],
  deterministicEvents: [{ stage: 'routingPolicy' }, { stage: 'citationGrounding' }],
  finalOutput: { recommendation: 'escalate' },
  redactions: ['Account holder names are redacted.'],
  nonClaims: ['This ledger exposes the prompt/response envelope VerdictAML controls; it is not DeepSeek chain-of-thought.'],
}

const runs: CopilotRunSummary[] = [
  {
    runId: 'run_123',
    alertId: 'HERO-002',
    mode: 'live',
    provider: 'deepseek',
    model: 'deepseek-v4-pro',
    status: 'completed',
    startedAt: '2026-07-07T12:00:00+08:00',
    completedAt: '2026-07-07T12:00:02+08:00',
    latencyMs: 2000,
    promptVersion: 'captured-runtime-envelope',
    outputHash: 'sha256:out',
    ledgerEndpoint: '/alerts/HERO-002/copilot-runs/run_123/ledger',
  },
]

describe('CopilotLedgerCard', () => {
  it('renders model-call envelope transparency without claiming chain-of-thought', () => {
    render(<CopilotLedgerCard runs={runs} ledger={ledger} />)

    expect(screen.getByText(/Copilot run ledger/i)).toBeTruthy()
    expect(screen.getByText(/Redacted prompt\/response envelope/i)).toBeTruthy()
    expect(screen.getByText('completed')).toBeTruthy()
    expect(screen.getByText('triageAgent')).toBeTruthy()
    expect(screen.getByText('verifier')).toBeTruthy()
    expect(screen.getAllByText('schema valid')).toHaveLength(2)
    expect(screen.getByText(/not DeepSeek chain-of-thought/i)).toBeTruthy()
    expect(screen.getByText(/2\/2 model response/i)).toBeTruthy()
  })

  it('shows unavailable state', () => {
    render(<CopilotLedgerCard runs={[]} ledger={null} />)

    expect(screen.getByText(/Prompt\/response ledger unavailable/i)).toBeTruthy()
  })
})
