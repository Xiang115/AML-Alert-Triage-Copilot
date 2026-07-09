import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { CollapsibleSection } from './CollapsibleSection'

describe('CollapsibleSection', () => {
  it('hides its content until the header is clicked (collapsed by default)', () => {
    render(
      <CollapsibleSection title="Provenance & controls">
        <p>governance internals</p>
      </CollapsibleSection>,
    )

    // The header (with its affordance) is always visible; the content is not, until expanded.
    expect(screen.getByText('Provenance & controls')).toBeTruthy()
    const toggle = screen.getByRole('button', { name: /Provenance & controls/i })
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByText('governance internals')).toBeNull()

    fireEvent.click(toggle)

    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByText('governance internals')).toBeTruthy()
  })

  it('starts open when defaultOpen is set', () => {
    render(
      <CollapsibleSection title="Open by default" defaultOpen>
        <p>visible immediately</p>
      </CollapsibleSection>,
    )

    expect(screen.getByText('visible immediately')).toBeTruthy()
  })
})
