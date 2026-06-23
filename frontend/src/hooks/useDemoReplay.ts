import { useCallback, useRef, useState } from 'react'
import type { Alert } from '../types'

const STEP_MS = 700 // gap between alerts streaming into the queue
const ANALYZE_MS = 400 // how long each row shows "Analyzing…" before its result

export interface DemoReplay {
  isReplaying: boolean
  visibleAlerts: Alert[]
  analyzingId: string | null
  start: (full: Alert[]) => void
  stop: () => void
}

/**
 * Drives the demo "replay": precomputed alerts stream into the queue one-by-one,
 * each briefly showing "Analyzing…" before snapping to its result, then HERO-001 is
 * opened (the wow). Pure animation over already-computed data — NO API/LLM calls.
 * Gated behind an explicit trigger so the normal load path stays untouched.
 */
export function useDemoReplay(onFinish: (alertId: string) => void): DemoReplay {
  const [isReplaying, setIsReplaying] = useState(false)
  const [visibleAlerts, setVisibleAlerts] = useState<Alert[]>([])
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const clearTimers = () => {
    timers.current.forEach(clearTimeout)
    timers.current = []
  }

  const stop = useCallback(() => {
    clearTimers()
    setIsReplaying(false)
    setAnalyzingId(null)
    setVisibleAlerts([])
  }, [])

  const start = useCallback(
    (full: Alert[]) => {
      clearTimers()
      setIsReplaying(true)
      setVisibleAlerts([])
      setAnalyzingId(null)

      full.forEach((alert, i) => {
        const appear = setTimeout(() => {
          setVisibleAlerts((prev) => [...prev, alert])
          setAnalyzingId(alert.alertId)
          const resolve = setTimeout(() => {
            setAnalyzingId((cur) => (cur === alert.alertId ? null : cur))
          }, ANALYZE_MS)
          timers.current.push(resolve)
        }, i * STEP_MS)
        timers.current.push(appear)
      })

      const finish = setTimeout(() => {
        setIsReplaying(false)
        setAnalyzingId(null)
        const hero = full.find((a) => a.alertId === 'HERO-001')
        const id = (hero ?? full[full.length - 1])?.alertId
        if (id) onFinish(id)
      }, full.length * STEP_MS + ANALYZE_MS)
      timers.current.push(finish)
    },
    [onFinish],
  )

  return { isReplaying, visibleAlerts, analyzingId, start, stop }
}
