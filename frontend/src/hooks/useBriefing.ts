import { useCallback, useEffect, useState } from 'react'
import { getBriefing } from '../api'
import type { ShiftBriefing } from '../types'

/** Loads the Queue Agent's Shift Briefing for the queue view (ADR-0010). */
export function useBriefing() {
  const [briefing, setBriefing] = useState<ShiftBriefing | null>(null)

  const reload = useCallback(() => {
    let active = true
    getBriefing()
      .then((b) => active && setBriefing(b))
      .catch(console.error)
    return () => {
      active = false
    }
  }, [])

  useEffect(() => reload(), [reload])

  return { briefing, reload }
}
