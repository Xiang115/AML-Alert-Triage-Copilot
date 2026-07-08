import { useEffect, useState } from 'react'
import { getGovernanceChangeRequests } from '../api'
import type { GovernanceChangeRequestList } from '../types'

/** Loads /governance/change-requests, refetching with the governance view. */
export function useGovernanceChangeRequests(activeTab: string) {
  const [changes, setChanges] = useState<GovernanceChangeRequestList | null>(null)

  useEffect(() => {
    getGovernanceChangeRequests().then(setChanges).catch(console.error)
  }, [activeTab])

  return changes
}
