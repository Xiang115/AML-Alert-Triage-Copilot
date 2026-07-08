import { useEffect, useState } from 'react'
import { getFinalsQADefense } from '../api'
import type { FinalsQADefensePacket } from '../types'

/** Loads /finals/qna-defense with the governance view. */
export function useFinalsQADefense(activeTab: string) {
  const [packet, setPacket] = useState<FinalsQADefensePacket | null>(null)

  useEffect(() => {
    getFinalsQADefense().then(setPacket).catch(console.error)
  }, [activeTab])

  return packet
}
