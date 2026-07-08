import { useEffect, useState } from 'react'
import { getQAOutcomes } from '../api'
import type { QAOutcomeSummary } from '../types'

/** Loads /qa/outcomes, refetching with the governance view. */
export function useQAOutcomes(activeTab: string) {
  const [summary, setSummary] = useState<QAOutcomeSummary | null>(null)

  useEffect(() => {
    getQAOutcomes().then(setSummary).catch(console.error)
  }, [activeTab])

  return summary
}
