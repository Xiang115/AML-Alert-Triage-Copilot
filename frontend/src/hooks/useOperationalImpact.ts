import { useEffect, useState } from 'react'
import { getOperationalImpact } from '../api'
import type { OperationalImpact } from '../types'

/** Loads /operations/impact, refetching with the governance view. */
export function useOperationalImpact(activeTab: string) {
  const [impact, setImpact] = useState<OperationalImpact | null>(null)

  useEffect(() => {
    getOperationalImpact().then(setImpact).catch(console.error)
  }, [activeTab])

  return impact
}
