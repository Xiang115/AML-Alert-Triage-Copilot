import { useEffect, useState } from 'react'
import { getAccessControlPosture } from '../api'
import type { AccessControlPosture } from '../types'

/** Loads /security/access-control, refetching with the governance view. */
export function useAccessControlPosture(activeTab: string) {
  const [posture, setPosture] = useState<AccessControlPosture | null>(null)

  useEffect(() => {
    getAccessControlPosture().then(setPosture).catch(console.error)
  }, [activeTab])

  return posture
}
