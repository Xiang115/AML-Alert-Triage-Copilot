import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

// Smoke test: render the whole composition against the mock api (fixtures), proving
// the data hooks + every panel mount and the queue populates without throwing.
describe('App (smoke)', () => {
  it('renders the shell and loads the queue from mock fixtures', async () => {
    render(<App />)

    // Static shell is present immediately.
    expect(screen.getByText('Alert Queue')).toBeTruthy()
    expect(screen.getByText('System Performance')).toBeTruthy()

    // Queue items arrive asynchronously from the mock api (SAML-D accounts, ADR-0012).
    expect((await screen.findAllByText(/SAML-D account/i)).length).toBeGreaterThan(0)

    // The Queue Agent's Shift Briefing renders (ADR-0010)...
    expect(await screen.findByText(/overnight run/i)).toBeTruthy()
    // ...and the default needsReview lane hides an auto-cleared alert (SD-00002) until you switch lanes.
    expect(screen.queryByText('SAML-D account 188929394')).toBeNull()

    // Nothing selected yet -> the empty-state prompt is shown.
    expect(screen.getByText(/choose an alert from the queue/i)).toBeTruthy()
  })
})
