import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DecisionPanel } from './DecisionPanel'

describe('DecisionPanel', () => {
  it('makes the accept and override dispositions explicit', () => {
    render(<DecisionPanel recommendation="dismiss" onApprove={vi.fn()} onOverride={vi.fn()} />)

    expect(screen.getByText('AI: Dismiss')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Accept AI Dismiss/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Override AI Escalate/i })).toBeTruthy()
  })

  it('requires a reason before overriding the AI', () => {
    const onOverride = vi.fn()
    render(<DecisionPanel recommendation="escalate" onApprove={vi.fn()} onOverride={onOverride} />)

    fireEvent.click(screen.getByRole('button', { name: /Override AI Dismiss/i }))

    expect(onOverride).not.toHaveBeenCalled()
    expect(screen.getByText(/Add a reason to override/i)).toBeTruthy()

    fireEvent.change(screen.getByPlaceholderText(/required to override/i), {
      target: { value: 'Known payroll corridor already cleared by compliance.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Override AI Dismiss/i }))

    expect(onOverride).toHaveBeenCalledWith('Known payroll corridor already cleared by compliance.')
  })
})
