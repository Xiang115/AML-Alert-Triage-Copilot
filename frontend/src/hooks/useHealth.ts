import { useEffect, useState } from 'react'
import { getHealth } from '../api'
import type { Health } from '../types'

/** Loads /health (active LLM provider + model), refetching whenever `activeTab` changes. */
export function useHealth(activeTab: string) {
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(console.error)
  }, [activeTab])

  return health
}
