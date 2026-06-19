import { useEffect, useState } from 'react'
import { getAlert } from '../api'
import type { Alert } from '../types'

/** Loads the embedded detail (transactions + triage) for the selected alert.
 *  Exposes `setAlert` so a live triage run can replace it without a refetch. */
export function useAlertDetail(alertId: string | null) {
  const [alert, setAlert] = useState<Alert | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // Fetch-on-select: clearing/loading state synchronously here is intentional.
    if (!alertId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAlert(null)
      return
    }
    setLoading(true)
    getAlert(alertId)
      .then(setAlert)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [alertId])

  return { alert, loading, setAlert }
}
