import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ShadowModeValidation } from './ShadowModeValidation'

describe('ShadowModeValidation', () => {
  it('states production auto-clear is locked until validation and approval', () => {
    render(<ShadowModeValidation />)

    expect(screen.getByText(/Shadow-mode validation gate/i)).toBeTruthy()
    expect(screen.getByText(/production auto-clear locked/i)).toBeTruthy()
    expect(screen.getByText(/auto-clear starts disabled/i)).toBeTruthy()
    expect(screen.getByText(/compliance approves the thresholds/i)).toBeTruthy()
  })

  it('shows the validation sequence from historical replay to monitoring', () => {
    render(<ShadowModeValidation />)

    expect(screen.getByText(/Historical replay/i)).toBeTruthy()
    expect(screen.getByText(/Known-outcome comparison/i)).toBeTruthy()
    expect(screen.getByText(/Threshold approval/i)).toBeTruthy()
    expect(screen.getByText(/Limited production auto-clear/i)).toBeTruthy()
    expect(screen.getByText(/Continuous monitoring/i)).toBeTruthy()
  })
})
