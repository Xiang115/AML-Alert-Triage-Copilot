import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AccessControlPostureCard } from './AccessControlPostureCard'
import type { AccessControlPosture } from '../types'

const posture: AccessControlPosture = {
  mode: 'actorRoleHeaders',
  demoFallbackActor: { actorId: 'demo-operator', actorRole: 'admin', source: 'demoFallback' },
  rules: [
    {
      endpoint: '/alerts/{alert_id}/decision',
      method: 'POST',
      allowedRoles: ['analyst', 'compliance', 'admin'],
      control: 'Only an analyst/compliance actor can approve or override the AI recommendation.',
      auditEvent: 'decision',
    },
    {
      endpoint: '/alerts/{alert_id}/str/submit',
      method: 'POST',
      allowedRoles: ['compliance', 'admin'],
      control: 'Filing requires an existing analyst escalation decision plus a compliance-capable actor.',
      auditEvent: 'submission',
    },
  ],
  fourEyesControls: ['STR submission is separated from the decision endpoint.'],
  nonClaims: ['This is not production SSO; it is the authorization seam a bank would bind to OIDC/JWT claims.'],
}

describe('AccessControlPostureCard', () => {
  it('renders role-gated writes, four-eyes controls, and non-claims', () => {
    render(<AccessControlPostureCard posture={posture} />)

    expect(screen.getByText('Access control posture')).toBeTruthy()
    expect(screen.getByText(/demo-operator/i)).toBeTruthy()
    expect(screen.getByText(/POST \/alerts\/\{alert_id\}\/decision/i)).toBeTruthy()
    expect(screen.getAllByText('compliance').length).toBeGreaterThan(0)
    expect(screen.getByText(/STR submission is separated/i)).toBeTruthy()
    expect(screen.getByText(/not production SSO/i)).toBeTruthy()
  })
})
