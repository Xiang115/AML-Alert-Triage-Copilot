import { useEffect, useState } from 'react'
import { getProductionTrustPlan } from '../api'
import type { ProductionTrustPlan } from '../types'

/** Loads /production/trust-plan, refetching with the governance view. */
export function useProductionTrustPlan(activeTab: string) {
  const [plan, setPlan] = useState<ProductionTrustPlan | null>(null)

  useEffect(() => {
    getProductionTrustPlan().then(setPlan).catch(console.error)
  }, [activeTab])

  return plan
}
