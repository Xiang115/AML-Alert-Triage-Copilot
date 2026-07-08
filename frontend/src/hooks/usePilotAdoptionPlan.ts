import { useEffect, useState } from 'react'
import { getPilotAdoptionPlan } from '../api'
import type { PilotAdoptionPlan } from '../types'

/** Loads /pilot/adoption-plan, refetching on tab change with the governance view. */
export function usePilotAdoptionPlan(activeTab: string) {
  const [plan, setPlan] = useState<PilotAdoptionPlan | null>(null)

  useEffect(() => {
    getPilotAdoptionPlan().then(setPlan).catch(console.error)
  }, [activeTab])

  return plan
}
