import { useEffect, useState } from 'react'
import { getFinalsDemoScript } from '../api'
import type { FinalsDemoScript } from '../types'

/** Loads /finals/demo-script, refetching with the governance view. */
export function useFinalsDemoScript(activeTab: string) {
  const [script, setScript] = useState<FinalsDemoScript | null>(null)

  useEffect(() => {
    getFinalsDemoScript().then(setScript).catch(console.error)
  }, [activeTab])

  return script
}
