import { useEffect, useState } from 'react'
import { getBriefing } from '../api'
import type { ShiftBriefing } from '../types'

/** Loads the Queue Agent's Shift Briefing once for the queue view (ADR-0010). */
export function useBriefing(): ShiftBriefing | null {
  const [briefing, setBriefing] = useState<ShiftBriefing | null>(null)
  useEffect(() => {
    let active = true
    getBriefing()
      .then((b) => active && setBriefing(b))
      .catch(console.error)
    return () => { active = false }
  }, [])
  return briefing
}
