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

    // Queue items arrive asynchronously from the mock api.
    expect(await screen.findByText('Tan Wei Ming')).toBeTruthy()

    // The Queue Agent's Shift Briefing renders (ADR-0010)...
    expect(await screen.findByText(/overnight run/i)).toBeTruthy()
    // ...and the default needsReview lane hides an auto-cleared alert until you switch lanes.
    expect(screen.queryByText('Priya Nair')).toBeNull()

    // Nothing selected yet -> the empty-state prompt is shown.
    expect(screen.getByText(/choose an alert from the queue/i)).toBeTruthy()
  })
})
