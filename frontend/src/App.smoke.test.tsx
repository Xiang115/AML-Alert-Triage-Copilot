// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from './App'

test('all tabs render in the DOM', () => {
  render(<App />)
  for (const label of ['Alert Queue', 'Learned Patterns', 'System Performance', 'Governance', 'Audit Trail']) {
    expect(screen.getByRole('button', { name: label })).toBeTruthy()
  }
})
