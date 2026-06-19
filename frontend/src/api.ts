// API client. Defaults to MOCK mode (reads fixtures) so the console builds
// without the backend running. Set VITE_MOCK=false to hit the live API.

import type { Alert, AlertStatus, Metrics, TriageResult, DecisionAction, Recommendation, STRDraft } from './types'
import alertsFixture from './fixtures/alerts.json'
import metricsFixture from './fixtures/metrics.json'

// Local state cache for mock mode to simulate database persistence
const mockAlerts: Alert[] = [...(alertsFixture as unknown as Alert[])]

const MOCK = import.meta.env.VITE_MOCK !== 'false'
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function getAlerts(status?: AlertStatus): Promise<Alert[]> {
  if (MOCK) {
    // Return alerts from local state.
    // In queue list (when status is queried), transactions are null to match backend contract.
    const list = mockAlerts.map((a) => ({ ...a, transactions: status ? null : a.transactions }))
    return status ? list.filter((a) => a.status === status) : list
  }
  const url = new URL('/alerts', BASE)
  if (status) url.searchParams.set('status', status)
  const r = await fetch(url)
  if (!r.ok) throw new Error(`GET /alerts ${r.status}`)
  return r.json()
}

export async function getAlert(alertId: string): Promise<Alert> {
  if (MOCK) {
    const alert = mockAlerts.find((a) => a.alertId === alertId)
    if (!alert) throw new Error(`Alert ${alertId} not found`)
    return { ...alert }
  }
  const r = await fetch(new URL(`/alerts/${alertId}`, BASE))
  if (!r.ok) throw new Error(`GET /alerts/${alertId} ${r.status}`)
  return r.json()
}

export async function postTriage(alertId: string): Promise<TriageResult> {
  if (MOCK) {
    // In mock mode, simulate a 1.5s live triage delay and return the precomputed triage.
    await new Promise((resolve) => setTimeout(resolve, 1500))
    const alert = mockAlerts.find((a) => a.alertId === alertId)
    if (!alert) throw new Error(`Alert ${alertId} not found`)
    return alert.triage
  }
  const r = await fetch(new URL(`/alerts/${alertId}/triage`, BASE), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!r.ok) throw new Error(`POST /alerts/${alertId}/triage ${r.status}`)
  return r.json()
}

export async function postDecision(
  alertId: string,
  action: DecisionAction,
  finalDisposition: Recommendation,
  editedStrDraft?: STRDraft | null
): Promise<Alert> {
  const nextStatus: AlertStatus = action === 'approve' ? 'approved' : 'overridden'

  if (MOCK) {
    const idx = mockAlerts.findIndex((a) => a.alertId === alertId)
    if (idx === -1) throw new Error(`Alert ${alertId} not found`)
    
    const updatedAlert = {
      ...mockAlerts[idx],
      status: nextStatus,
      triage: {
        ...mockAlerts[idx].triage,
        strDraft: editedStrDraft !== undefined ? editedStrDraft : mockAlerts[idx].triage.strDraft,
      },
    }
    mockAlerts[idx] = updatedAlert
    return { ...updatedAlert }
  }

  const r = await fetch(new URL(`/alerts/${alertId}/decision`, BASE), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, finalDisposition, editedStrDraft }),
  })
  if (!r.ok) throw new Error(`POST /alerts/${alertId}/decision ${r.status}`)
  return r.json()
}

export async function getMetrics(): Promise<Metrics> {
  if (MOCK) return metricsFixture as Metrics
  const r = await fetch(new URL('/metrics', BASE))
  if (!r.ok) throw new Error(`GET /metrics ${r.status}`)
  return r.json()
}
