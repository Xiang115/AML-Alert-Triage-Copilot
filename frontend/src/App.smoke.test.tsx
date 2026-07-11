// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from './App'

test('default view keeps only the essentials; Expert view reveals the rest', () => {
  render(<App />)

  // Analyst default: just the queue and the Expert view toggle.
  expect(screen.getByRole('button', { name: 'Alert Queue' })).toBeTruthy()
  for (const label of ['Learned Patterns', 'System Performance', 'Governance', 'Audit Trail']) {
    expect(screen.queryByRole('button', { name: label })).toBeNull()
  }

  // Expert view brings every reviewer/regulator tab back.
  fireEvent.click(screen.getByRole('button', { name: 'Expert view' }))
  for (const label of ['Alert Queue', 'Learned Patterns', 'System Performance', 'Governance', 'Audit Trail']) {
    expect(screen.getByRole('button', { name: label })).toBeTruthy()
  }
})
