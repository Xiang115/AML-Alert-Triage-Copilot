import { useEffect, useState } from 'react'
import { getIntegrationContract } from '../api'
import type { BankIntegrationContract } from '../types'

/** Loads /integration/contract, refetching on tab change with the governance view. */
export function useIntegrationContract(activeTab: string) {
  const [contract, setContract] = useState<BankIntegrationContract | null>(null)

  useEffect(() => {
    getIntegrationContract().then(setContract).catch(console.error)
  }, [activeTab])

  return contract
}
