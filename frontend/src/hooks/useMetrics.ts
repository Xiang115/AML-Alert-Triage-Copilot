import { useEffect, useState } from 'react'
import { getMetrics } from '../api'
import type { Metrics } from '../types'

/** Loads dashboard metrics, refetching whenever `activeTab` changes. */
export function useMetrics(activeTab: string) {
  const [metrics, setMetrics] = useState<Metrics | null>(null)

  useEffect(() => {
    getMetrics().then(setMetrics).catch(console.error)
  }, [activeTab])

  return metrics
}
