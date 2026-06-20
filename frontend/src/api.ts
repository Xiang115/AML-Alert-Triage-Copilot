// API client. Defaults to MOCK mode (reads fixtures) so the console builds
// without the backend running. Set VITE_MOCK=false to hit the live API.

import type { Alert, AlertStatus, AuditEntry, Metrics, SubmissionAck, TriageResult, DecisionAction, Recommendation, STRDraft } from './types'
import { resolveStrDraft } from './decision'
import alertsFixture from './fixtures/alerts.json'
import metricsFixture from './fixtures/metrics.json'

// Local state cache for mock mode to simulate database persistence
const mockAlerts: Alert[] = [...(alertsFixture as unknown as Alert[])]
// Append-only audit trail for mock mode (mirrors the backend _AUDIT_LOG).
const mockAudit: AuditEntry[] = []

// Demo-stable FIU ref, mirroring backend goaml.submission_reference.
function mockSubmissionRef(alertId: string): string {
  let h = 0
  for (let i = 0; i < alertId.length; i++) h = (h * 31 + alertId.charCodeAt(i)) >>> 0
  return `MYFIU-2026-${String(h % 1_000_000).padStart(6, '0')}`
}

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
  editedStrDraft?: STRDraft | null,
  note?: string | null
): Promise<Alert> {
  const nextStatus: AlertStatus = action === 'approve' ? 'approved' : 'overridden'

  if (MOCK) {
    const idx = mockAlerts.findIndex((a) => a.alertId === alertId)
    if (idx === -1) throw new Error(`Alert ${alertId} not found`)

    const triage = mockAlerts[idx].triage
    mockAudit.push({
      alertId, event: 'decision', at: new Date().toISOString(), action,
      aiRecommendation: triage.recommendation, finalDisposition,
      confidence: triage.confidence, verifierStatus: triage.verifier.status, note: note ?? null,
    })
    const updatedAlert = {
      ...mockAlerts[idx],
      status: nextStatus,
      triage: {
        ...triage,
        // Apply the same disposition->STR rule the backend enforces.
        strDraft: resolveStrDraft(finalDisposition, editedStrDraft, triage.strDraft),
      },
    }
    mockAlerts[idx] = updatedAlert
    return { ...updatedAlert }
  }

  const r = await fetch(new URL(`/alerts/${alertId}/decision`, BASE), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, finalDisposition, editedStrDraft, note }),
  })
  if (!r.ok) throw new Error(`POST /alerts/${alertId}/decision ${r.status}`)
  return r.json()
}

// goAML STR export (the integration seam). Always hits the live backend — the XML
// is the real serializer's XSD-validated output, not a mock. The backend gates this
// on an escalate sign-off, so it 409s unless the alert was approved/overridden to
// escalate (mirrored by `canExport` in the UI). Triggers a file download.
export async function exportGoamlStr(alertId: string): Promise<void> {
  const r = await fetch(new URL(`/alerts/${alertId}/str.xml`, BASE))
  if (!r.ok) throw new Error(`GET /alerts/${alertId}/str.xml ${r.status}`)
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `goAML-STR-${alertId}.xml`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// File the approved STR to goAML and return the FIU acknowledgement. Gated server-side
// on an escalate sign-off (same gate as export), recorded in the audit trail.
export async function submitGoamlStr(alertId: string): Promise<SubmissionAck> {
  if (MOCK) {
    const ack: SubmissionAck = {
      alertId, submissionRef: mockSubmissionRef(alertId), status: 'accepted',
      submittedAt: new Date().toISOString(),
    }
    mockAudit.push({ alertId, event: 'submission', at: ack.submittedAt, submissionRef: ack.submissionRef })
    return ack
  }
  const r = await fetch(new URL(`/alerts/${alertId}/str/submit`, BASE), { method: 'POST' })
  if (!r.ok) throw new Error(`POST /alerts/${alertId}/str/submit ${r.status}`)
  return r.json()
}

export async function getAudit(): Promise<AuditEntry[]> {
  if (MOCK) return [...mockAudit].reverse()
  const r = await fetch(new URL('/audit', BASE))
  if (!r.ok) throw new Error(`GET /audit ${r.status}`)
  return r.json()
}

export async function getMetrics(): Promise<Metrics> {
  if (MOCK) return metricsFixture as Metrics
  const r = await fetch(new URL('/metrics', BASE))
  if (!r.ok) throw new Error(`GET /metrics ${r.status}`)
  return r.json()
}
