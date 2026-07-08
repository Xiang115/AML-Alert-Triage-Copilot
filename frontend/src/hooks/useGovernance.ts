import { useEffect, useState } from 'react'
import { getGovernance } from '../api'
import type { Governance } from '../types'

/** Loads /governance (model, thresholds, last validation, override rate), refetching on tab change. */
export function useGovernance(activeTab: string) {
  const [governance, setGovernance] = useState<Governance | null>(null)

  useEffect(() => {
    getGovernance().then(setGovernance).catch(console.error)
  }, [activeTab])

  return governance
}
