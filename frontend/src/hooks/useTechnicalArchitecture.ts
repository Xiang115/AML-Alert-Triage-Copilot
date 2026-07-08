import { useEffect, useState } from 'react'
import { getTechnicalArchitecture } from '../api'
import type { TechnicalArchitecture } from '../types'

/** Loads /architecture/technical, refetching with the governance view. */
export function useTechnicalArchitecture(activeTab: string) {
  const [architecture, setArchitecture] = useState<TechnicalArchitecture | null>(null)

  useEffect(() => {
    getTechnicalArchitecture().then(setArchitecture).catch(console.error)
  }, [activeTab])

  return architecture
}
