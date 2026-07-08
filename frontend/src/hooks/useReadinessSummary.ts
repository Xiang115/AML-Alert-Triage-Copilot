import { useEffect, useState } from 'react'
import { getReadinessSummary } from '../api'
import type { ReadinessSummary } from '../types'

/** Loads /readiness/summary, refetching on tab change with the governance view. */
export function useReadinessSummary(activeTab: string) {
  const [summary, setSummary] = useState<ReadinessSummary | null>(null)

  useEffect(() => {
    getReadinessSummary().then(setSummary).catch(console.error)
  }, [activeTab])

  return summary
}
