import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDemoReplay } from './useDemoReplay'
import type { Alert } from '../types'

const mk = (id: string): Alert => ({ alertId: id }) as unknown as Alert

describe('useDemoReplay', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('streams alerts in one-by-one, then opens HERO-001 at the end', () => {
    const onFinish = vi.fn()
    const full = [mk('DQ-001'), mk('HERO-001'), mk('DQ-002')]
    const { result } = renderHook(() => useDemoReplay(onFinish))

    act(() => result.current.start(full))

    // first alert appears and shows "Analyzing…"
    act(() => vi.advanceTimersByTime(1))
    expect(result.current.visibleAlerts.map((a) => a.alertId)).toEqual(['DQ-001'])
    expect(result.current.analyzingId).toBe('DQ-001')

    // its analyzing state resolves
    act(() => vi.advanceTimersByTime(400))
    expect(result.current.analyzingId).toBeNull()

    // run to completion
    act(() => vi.advanceTimersByTime(5000))
    expect(result.current.visibleAlerts).toHaveLength(3)
    expect(result.current.isReplaying).toBe(false)
    expect(onFinish).toHaveBeenCalledWith('HERO-001')
  })

  it('stop() cancels timers and resets state', () => {
    const onFinish = vi.fn()
    const { result } = renderHook(() => useDemoReplay(onFinish))

    act(() => result.current.start([mk('DQ-001'), mk('DQ-002')]))
    act(() => result.current.stop())

    expect(result.current.isReplaying).toBe(false)
    expect(result.current.visibleAlerts).toEqual([])
    expect(result.current.analyzingId).toBeNull()

    // no finish callback fires after stop
    act(() => vi.advanceTimersByTime(5000))
    expect(onFinish).not.toHaveBeenCalled()
  })
})
