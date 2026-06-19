import { useCallback, useEffect, useState } from 'react'
import { getAlerts } from '../api'
import type { Alert, AlertStatus } from '../types'

/** Loads the alert queue for the active status filter, with a manual `reload`. */
export function useAlerts(filterStatus: AlertStatus | 'all') {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)

  const reload = useCallback(() => {
    setLoading(true)
    getAlerts(filterStatus === 'all' ? undefined : filterStatus)
      .then(setAlerts)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [filterStatus])

  useEffect(() => {
    // Fetch-on-mount/refilter: the loading flag set inside reload() is intentional.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload()
  }, [reload])

  return { alerts, loading, reload }
}
