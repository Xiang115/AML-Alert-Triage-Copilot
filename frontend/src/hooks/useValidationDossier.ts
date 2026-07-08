import { useEffect, useState } from 'react'
import { getValidationDossier } from '../api'
import type { ValidationDossier } from '../types'

/** Loads /governance/validation-dossier, refetching on tab change with the governance view. */
export function useValidationDossier(activeTab: string) {
  const [dossier, setDossier] = useState<ValidationDossier | null>(null)

  useEffect(() => {
    getValidationDossier().then(setDossier).catch(console.error)
  }, [activeTab])

  return dossier
}
