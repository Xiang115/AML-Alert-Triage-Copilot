import { describe, it, expect } from 'vitest'
import { finalDispositionFor, resolveStrDraft } from './decision'
import type { STRDraft } from './types'

const draft = { activitySummary: 'x' } as unknown as STRDraft

describe('finalDispositionFor', () => {
  it('keeps the disposition on approve', () => {
    expect(finalDispositionFor('escalate', 'approve')).toBe('escalate')
    expect(finalDispositionFor('dismiss', 'approve')).toBe('dismiss')
  })
  it('flips the disposition on override', () => {
    expect(finalDispositionFor('escalate', 'override')).toBe('dismiss')
    expect(finalDispositionFor('dismiss', 'override')).toBe('escalate')
  })
})

describe('resolveStrDraft', () => {
  it('drops the draft when dismissing', () => {
    expect(resolveStrDraft('dismiss', draft, draft)).toBeNull()
  })
  it('keeps the current draft when escalating without an edit', () => {
    expect(resolveStrDraft('escalate', undefined, draft)).toBe(draft)
  })
  it('replaces with the analyst edit when escalating', () => {
    const edited = { activitySummary: 'edited' } as unknown as STRDraft
    expect(resolveStrDraft('escalate', edited, draft)).toBe(edited)
  })
})
