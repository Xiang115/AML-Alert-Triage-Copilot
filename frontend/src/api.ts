// API client. Defaults to MOCK mode (reads fixtures) so the console builds
// without the backend running. Set VITE_MOCK=false to hit the live API.

import type { Alert, AlertStatus, Metrics } from './types'
import alertsFixture from './fixtures/alerts.json'
import metricsFixture from './fixtures/metrics.json'

const MOCK = import.meta.env.VITE_MOCK !== 'false'
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function getAlerts(status?: AlertStatus): Promise<Alert[]> {
  if (MOCK) {
    const queue = (alertsFixture as unknown as Alert[]).map((a) => ({ ...a, transactions: null }))
    return status ? queue.filter((a) => a.status === status) : queue
  }
  const url = new URL('/alerts', BASE)
  if (status) url.searchParams.set('status', status)
  const r = await fetch(url)
  if (!r.ok) throw new Error(`GET /alerts ${r.status}`)
  return r.json()
}

export async function getMetrics(): Promise<Metrics> {
  if (MOCK) return metricsFixture as Metrics
  const r = await fetch(new URL('/metrics', BASE))
  if (!r.ok) throw new Error(`GET /metrics ${r.status}`)
  return r.json()
}
