import { useEffect, useState } from 'react'
import { getInnovationDifferentiation } from '../api'
import type { InnovationDifferentiation } from '../types'

/** Loads /innovation/differentiation with the governance view. */
export function useInnovationDifferentiation(activeTab: string) {
  const [differentiation, setDifferentiation] = useState<InnovationDifferentiation | null>(null)

  useEffect(() => {
    getInnovationDifferentiation().then(setDifferentiation).catch(console.error)
  }, [activeTab])

  return differentiation
}
