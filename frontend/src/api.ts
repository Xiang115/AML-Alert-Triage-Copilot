// API client. Defaults to MOCK mode (reads fixtures) so the console builds
// without the backend running. Set VITE_MOCK=false to hit the live API.

import type { AccessControlPosture, ActorRole, Alert, AlertStatus, AuditEntry, BankIntegrationContract, BlockedReason, CaseHandoff, CoachingHandbook, CopilotRunLedger, CopilotRunList, DecisionSummary, DecisionTrace, DecisionTraceStep, Evaluation, FinalsDemoScript, FinalsQADefensePacket, Governance, GovernanceChangeRequestList, Health, InnovationDifferentiation, Metrics, MuleNetwork, OperationalImpact, PilotAdoptionPlan, ProductionTrustPlan, QAOutcome, QAOutcomeSummary, QueueNextAction, ReadinessSummary, ShiftBriefing, SubmissionAck, Suppression, SuppressionFrontier, TechnicalArchitecture, TriageResult, DecisionAction, Recommendation, STRDraft, ValidationDossier, VerifierStatus } from './types'
import { finalDispositionFor, resolveStrDraft } from './decision'
import { AUTO_CLEAR_THRESHOLD, REVIEW_THRESHOLD, effectiveRouting, envelopeBenignConsistent } from './routing'
import alertsFixture from './fixtures/alerts.json'
import ibmAlertsFixture from './fixtures/ibmAlerts.json'
import clusterAlertsFixture from './fixtures/clusterAlerts.json'
import metricsFixture from './fixtures/metrics.json'
import evaluationFixture from './fixtures/evaluation.json'
import networksFixture from './fixtures/networks.json'
import suppressionFrontierFixture from './fixtures/suppressionFrontier.json'

// Local state cache for mock mode to simulate database persistence. The IBM hidden-mule seed
// alert (ADR-0015) joins the SAML-D catalog so opening it → revealing its network plays beat 2.
const mockAlerts: Alert[] = [
  ...(alertsFixture as unknown as Alert[]),
  ...(ibmAlertsFixture as unknown as Alert[]),
  ...(clusterAlertsFixture as unknown as Alert[]),  // Slice A beat-3 self-suppression cluster
]
// Append-only audit trail for mock mode (mirrors the backend _AUDIT_LOG).
const mockAudit: AuditEntry[] = []
const mockQaOutcomes: QAOutcome[] = []

// Seed the mock trail with the Queue Agent's autoClear events, so /audit opens populated
// in mock mode exactly like the backend audit seed (ADR-0010). Pushed first (oldest); a
// later getAudit() reverses to newest-first.
const QUEUE_AGENT_RUN_AT = '2026-06-23T06:00:00'
for (const a of mockAlerts) {
  if (a.routing === 'autoCleared') {
    mockAudit.push({
      alertId: a.alertId, event: 'autoClear', at: QUEUE_AGENT_RUN_AT,
      aiRecommendation: a.triage.recommendation, confidence: a.triage.confidence,
      verifierStatus: a.triage.verifier.status,
    })
  }
}

// Seed debateResolved events for contested calls (ADR-0011), mirroring the backend's
// build_debate_audit_seed, so /audit shows every adversarial debate in mock mode too.
for (const a of mockAlerts) {
  if (a.triage.debate) {
    mockAudit.push({
      alertId: a.alertId, event: 'debateResolved', at: QUEUE_AGENT_RUN_AT,
      aiRecommendation: a.triage.recommendation, verifierStatus: a.triage.verifier.status,
      note: a.triage.debate.reverdict.note,
    })
  }
}

// --- Slice A: mock suppression, mirroring the backend (agents/memory.py + store.cleared_patterns).
// The mock client learns a cleared pattern on a dismiss and enriches a served alert with a
// suppression when its behavioral-envelope signature matches — the SAME deterministic logic the
// backend runs, so the demo drives the real dismiss->suppress loop, not a hardcoded banner.
interface MockClearedPattern {
  signature: string
  typology: string | null
  sourceDecisionId: string
  sourceAlertId: string
  clearedCount: number
  clearedAt: string
}

const mockClearedPatterns = new Map<string, MockClearedPattern>()
// Demo initial state: a benign PT-01 counterparty the team cleared on prior alerts (kept in sync
// with fixtures/learnedPatterns.json). Makes SD-00006 open pre-suppressed, citing the real
// SD-00004 decision; dismissing any alert below learns a new pattern the same way.
mockClearedPatterns.set('typ=PT-01|amt=5|dir=mix|drain=False|conc=0|xb=1|cash=1|ntxn=5', {
  signature: 'typ=PT-01|amt=5|dir=mix|drain=False|conc=0|xb=1|cash=1|ntxn=5', typology: 'PT-01',
  sourceDecisionId: 'SD-00004', sourceAlertId: 'SD-00004',
  clearedCount: 2, clearedAt: '2026-07-01T09:14:00+08:00',
})
mockClearedPatterns.clear()
mockClearedPatterns.set('typ=PT-01|amt=5|dir=mix|drain=False|conc=0|xb=1|cash=1|ntxn=5', {
  signature: 'typ=PT-01|amt=5|dir=mix|drain=False|conc=0|xb=1|cash=1|ntxn=5', typology: 'PT-01',
  sourceDecisionId: 'SD-00004', sourceAlertId: 'SD-00004',
  clearedCount: 2, clearedAt: '2026-07-01T09:14:00+08:00',
})

const AMT_EDGES = [1e3, 5e3, 1e4, 5e4, 1e5, 5e5]

function behavioralAmtBand(x: number): number {
  for (let i = 0; i < AMT_EDGES.length; i += 1) {
    if (x <= AMT_EDGES[i]) return i
  }
  return 6
}

function behavioralBand3(share: number): number {
  if (share === 0) return 0
  return share >= 0.999 ? 2 : 1
}

function behavioralDirShape(inCount: number, outCount: number): 'in' | 'out' | 'mix' {
  if (outCount === 0) return 'in'
  if (inCount === 0) return 'out'
  return 'mix'
}

function behavioralConcBand(topShare: number): number {
  if (topShare < 0.5) return 0
  return topShare < 0.8 ? 1 : 2
}

function dominantCounterparty(alert: Alert): string | null {
  const txns = alert.transactions ?? []
  const cited = new Set(alert.triage.citedTransactionIds ?? [])
  const pool = txns.filter((t) => cited.has(t.transactionId))
  const keys = (pool.length ? pool : txns)
    .map((t) => (t.counterpartyAccount || t.counterpartyName || '').trim().toLowerCase())
    .filter(Boolean)
  if (!keys.length) return null
  const counts = new Map<string, number>()
  for (const key of keys) counts.set(key, (counts.get(key) ?? 0) + 1)
  let best = keys[0]
  let bestN = 0
  for (const [key, count] of counts) {
    if (count > bestN) {
      best = key
      bestN = count
    }
  }
  return best
}

function behavioralSignatureValue(value: string | number | boolean): string {
  if (typeof value === 'boolean') return value ? 'True' : 'False'
  return String(value)
}

function behavioralSignature(alert: Alert): string | null {
  const typology = alert.triage.matchedTypology.code
  const txns = alert.transactions ?? []
  if (typology === 'NONE' || txns.length === 0) return null

  const inCount = txns.filter((t) => t.direction === 'inbound').length
  const outCount = txns.filter((t) => t.direction === 'outbound').length
  const totalAmount = txns.reduce((sum, t) => sum + t.amount, 0)
  const counts = new Map<string, number>()
  for (const tx of txns) {
    const key = tx.counterpartyAccount || tx.counterpartyName || 'unknown'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  const topShare = txns.length ? Math.max(...Array.from(counts.values())) / txns.length : 0
  const crossBorderShare = txns.length ? txns.filter((t) => t.flags.includes('cross-border')).length / txns.length : 0
  const cashShare = txns.length ? txns.filter((t) => t.flags.includes('cash')).length / txns.length : 0

  const env = {
    typ: typology,
    amt: behavioralAmtBand(totalAmount),
    dir: behavioralDirShape(inCount, outCount),
    drain: !envelopeBenignConsistent(txns),
    conc: behavioralConcBand(topShare),
    xb: behavioralBand3(crossBorderShare),
    cash: behavioralBand3(cashShare),
    ntxn: Math.min(txns.length, 5),
  }

  return ['typ', 'amt', 'dir', 'drain', 'conc', 'xb', 'cash', 'ntxn']
    .map((key) => `${key}=${behavioralSignatureValue(env[key as keyof typeof env])}`)
    .join('|')
}

// Consolidation-account (hub) index from the network fixtures — mirror of agents.network_revocation.
// Maps a hub accountId (lowercased) -> its network id + holder, so a cleared counterparty that is a
// mule-network hub gets its suppression revoked (ADR-0021).
const mockHubs = new Map<string, { networkId: string; hubHolder: string }>()
for (const net of Object.values(networksFixture as Record<string, { seedAlertId: string; nodes: { role: string; accountId?: string; holderName?: string }[] }>)) {
  for (const n of net.nodes ?? []) {
    if (n.role === 'hub' && n.accountId) {
      mockHubs.set(String(n.accountId).toLowerCase(), { networkId: net.seedAlertId, hubHolder: n.holderName ?? n.accountId })
    }
  }
}

// Serve-time suppression enrichment — mirror of agents/memory.suppress (+ network_revocation).
function mockSuppress(alert: Alert): Suppression | null {
  const sig = behavioralSignature(alert)
  if (!sig) return null
  const p = mockClearedPatterns.get(sig)
  if (!p) return null
  const cp = dominantCounterparty(alert)
  const code = alert.triage.matchedTypology.code
  const base = {
    matchedPatternId: sig,
    sourceDecisionId: p.sourceDecisionId,
    sourceAlertId: p.sourceAlertId,
    signature: sig,
    clearedCount: p.clearedCount,
    clearedAt: p.clearedAt,
  }
  // Network Revocation (ADR-0021): the mule-network walk polices the memory.
  const hub = cp ? mockHubs.get(cp) : undefined
  if (hub) {
    return {
      ...base,
      status: 'revoked',
      revokedNetworkId: hub.networkId,
      rationale: `Counterparty ${cp} was cleared as benign on ${p.clearedCount} prior alert(s), but the mule-network walk flags it as a consolidation hub (${hub.hubHolder}) in network ${hub.networkId}. Suppression REVOKED — routed to human review.`,
    }
  }
  return {
    ...base,
    status: 'suppressed',
    rationale: `A benign look-alike with the same behavioral envelope (typology ${code}, matching amount band, flow direction, and ledger structure) was cleared on ${p.clearedCount} prior alert(s). Suppression cites decision ${p.sourceDecisionId}.`,
  }
}

// Learn a suppression pattern from a benign dismiss — mirror of decision.learn_from_decision.
function mockLearnFromDecision(alert: Alert, finalDisposition: Recommendation): void {
  if (finalDisposition !== 'dismiss') return
  const sig = behavioralSignature(alert)
  if (!sig) return
  const existing = mockClearedPatterns.get(sig)
  mockClearedPatterns.set(sig, {
    signature: sig,
    typology: alert.triage.matchedTypology.code,
    sourceDecisionId: alert.alertId,
    sourceAlertId: alert.alertId,
    clearedCount: (existing?.clearedCount ?? 0) + 1,
    clearedAt: new Date().toISOString(),
  })
}

// Demo-stable FIU ref, mirroring backend goaml.submission_reference.
function mockSubmissionRef(alertId: string): string {
  let h = 0
  for (let i = 0; i < alertId.length; i++) h = (h * 31 + alertId.charCodeAt(i)) >>> 0
  return `MYFIU-2026-${String(h % 1_000_000).padStart(6, '0')}`
}

function mockCaseStatusUpdate(alert: Alert, auditEvents: AuditEntry[]): CaseHandoff['caseStatusUpdate'] {
  if (auditEvents.some((e) => e.event === 'submission')) return 'filed'
  const decision = auditEvents.find((e) => e.event === 'decision')
  if (decision?.finalDisposition === 'escalate') return 'escalated'
  if (decision?.finalDisposition === 'dismiss') return 'dismissed'
  if (alert.routing === 'autoCleared') return 'autoCleared'
  return 'needsReview'
}

function mockCaseHandoff(alert: Alert): CaseHandoff {
  const auditEvents = [...mockAudit].reverse().filter((e) => e.alertId === alert.alertId)
  const decision = auditEvents.find((e) => e.event === 'decision')
  const statusUpdate = mockCaseStatusUpdate(alert, auditEvents)
  const submissionRef = auditEvents.find((e) => e.event === 'submission')?.submissionRef ?? null
  const canExport = !!decision && decision.finalDisposition === 'escalate' && !!alert.triage.strDraft
  const fired = alert.triage.indicatorCoverage.fired.length
  const total = alert.triage.indicatorCoverage.indicators.length
  const noteAction = submissionRef
    ? 'Approved STR filed to goAML'
    : decision?.finalDisposition
      ? `Human final disposition: ${decision.finalDisposition}`
      : statusUpdate === 'autoCleared'
        ? 'Queue Agent auto-cleared in demo shadow mode'
        : 'Routed to analyst review'

  return {
    alertId: alert.alertId,
    generatedAt: new Date().toISOString(),
    sourceSystem: 'VerdictAML case handoff API',
    targetSystems: ['SAS AML', 'NICE Actimize', 'Oracle Mantas', 'bank case-management queue', 'goAML e-filing seam'],
    caseStatusUpdate: statusUpdate,
    caseNote: `${noteAction}. AI recommended ${alert.triage.recommendation} at ${Math.round(alert.triage.confidence * 100)}% confidence on ${alert.triage.matchedTypology.code} (${alert.triage.matchedTypology.name}); verifier ${alert.triage.verifier.status}; ${fired}/${total} indicators fired; ${alert.triage.citedTransactionIds.length} cited transaction(s).`,
    decision: {
      aiRecommendation: alert.triage.recommendation,
      confidence: alert.triage.confidence,
      verifierStatus: alert.triage.verifier.status,
      finalDisposition: decision?.finalDisposition ?? null,
      decisionAction: decision?.action ?? null,
      overrideReason: decision?.action === 'override' ? decision.note ?? null : null,
    },
    attachments: [
      {
        name: 'Per-alert defense case',
        endpoint: `/alerts/${alert.alertId}/defense-case`,
        available: true,
        reason: 'Evidence, controls, and audit replay are always attached.',
      },
      {
        name: 'goAML STR XML',
        endpoint: `/alerts/${alert.alertId}/str.xml`,
        available: canExport,
        reason: canExport
          ? 'Unlocked after human escalate sign-off and STR anchoring checks.'
          : 'Locked until human escalate sign-off and STR anchoring checks pass.',
      },
      {
        name: 'Audit trail',
        endpoint: '/audit',
        available: auditEvents.length > 0,
        reason: `${auditEvents.length} event(s) recorded for this alert.`,
      },
    ],
    auditEvents,
    submissionRef,
    writeBack: {
      mode: decision ? 'humanApprovedWriteback' : 'shadowOnly',
      allowed: !!decision,
      requiresHumanDecision: true,
      blockedReason: decision ? null : 'No analyst final disposition yet; VerdictAML returns a shadow packet and does not mutate the bank case.',
      productionGate: 'Enable write-back only after bank historical replay, compliance approval, and case-management integration sign-off.',
    },
    nonClaims: [
      'This demo endpoint does not mutate a live bank case-management system.',
      'Auto-cleared alerts are inspectable and QA-sampled; they are not STR filings.',
      'goAML filing remains human-approved and evidence-anchored.',
    ],
  }
}

function mockDecisionTrace(alert: Alert): DecisionTrace {
  const auditEvents = [...mockAudit].reverse().filter((e) => e.alertId === alert.alertId)
  const decision = auditEvents.find((e) => e.event === 'decision')
  const coverage = alert.triage.indicatorCoverage
  const fired = new Set(coverage.fired)
  const citedIds = alert.triage.citedTransactionIds
  const screening = alert.triage.screening
  const suppression = alert.triage.suppression
  const finalDisposition = decision?.finalDisposition ?? null
  const canFile = !!decision && finalDisposition === 'escalate' && !!alert.triage.strDraft
  const steps: DecisionTraceStep[] = coverage.indicators.map((indicator) => {
    const active = fired.has(indicator)
    return {
      step: 'indicatorEvaluation',
      label: indicator,
      inputs: { matchedTypology: alert.triage.matchedTypology.code, indicator },
      result: active ? 'fired' : 'notFired',
      evidenceIds: active ? citedIds : [],
      deterministic: true,
    }
  })

  steps.push(
    {
      step: 'confidenceComputation',
      label: 'Served confidence',
      inputs: {
        firedIndicatorCount: coverage.fired.length,
        totalIndicatorCount: coverage.indicators.length,
        servedConfidence: alert.triage.confidence,
        matchedTypology: alert.triage.matchedTypology.code,
      },
      result: String(alert.triage.confidence),
      evidenceIds: citedIds,
      deterministic: true,
    },
    {
      step: 'verifierGate',
      label: 'Verifier agreement',
      inputs: {
        status: alert.triage.verifier.status,
        agreesWithRecommendation: alert.triage.verifier.agreesWithRecommendation,
        claims: (alert.triage.verifier.claims ?? []).map((c) => c.text).join('; '),
      },
      result: alert.triage.verifier.status,
      evidenceIds: citedIds,
      deterministic: false,
    },
    {
      step: 'screeningGate',
      label: 'Sanctions and PEP screening',
      inputs: {
        status: screening?.status ?? null,
        blocked: screening?.blocked ?? false,
        matches: screening?.matches.length ?? 0,
      },
      result: screening?.blocked ? 'screening:blocked' : 'screening:clear',
      evidenceIds: [],
      deterministic: true,
    },
    {
      step: 'debateGate',
      label: 'Adversarial debate',
      inputs: {
        present: !!alert.triage.debate,
        outcome: alert.triage.debate?.reverdict.outcome ?? null,
      },
      result: alert.triage.debate ? 'present' : 'absent',
      evidenceIds: alert.triage.debate ? citedIds : [],
      deterministic: false,
    },
    {
      step: 'suppressionGate',
      label: 'Learned suppression',
      inputs: {
        status: suppression?.status ?? null,
        matchedPatternId: suppression?.matchedPatternId ?? null,
        sourceDecisionId: suppression?.sourceDecisionId ?? null,
      },
      result: suppression?.status ?? 'absent',
      evidenceIds: suppression?.sourceDecisionId ? [suppression.sourceDecisionId] : [],
      deterministic: true,
    },
    {
      step: 'routePolicy',
      label: 'Queue routing policy',
      inputs: {
        recommendation: alert.triage.recommendation,
        confidence: alert.triage.confidence,
        routing: alert.routing,
        reviewThreshold: GOVERNANCE_THRESHOLDS.review,
        autoClearThreshold: GOVERNANCE_THRESHOLDS.autoClear,
        verifierStatus: alert.triage.verifier.status,
        screeningBlocked: screening?.blocked ?? false,
        debatePresent: !!alert.triage.debate,
        suppressionStatus: suppression?.status ?? null,
      },
      result: alert.routing ?? 'needsReview',
      evidenceIds: citedIds,
      deterministic: true,
    },
    {
      step: 'strFilingGate',
      label: 'STR/goAML filing gate',
      inputs: {
        finalDisposition,
        strDraftPresent: !!alert.triage.strDraft,
        anchoringExportBlocked: false,
        requiresHumanEscalateSignoff: true,
      },
      result: canFile ? 'canFile' : 'locked',
      evidenceIds: alert.triage.strDraft ? citedIds : [],
      deterministic: true,
    },
  )

  return {
    alertId: alert.alertId,
    generatedAt: new Date().toISOString(),
    currentRecommendation: alert.triage.recommendation,
    currentConfidence: alert.triage.confidence,
    routing: alert.routing,
    formula: coverage.indicators.length
      ? 'confidence = firedIndicators / totalIndicators, persisted from the served triage output'
      : 'confidence = 1.0 when no covered typology indicators matched (NONE)',
    steps,
    nonClaims: [
      'This trace is not DeepSeek chain-of-thought and does not expose private model reasoning.',
      'This endpoint does not rerun the LLM; it replays stored triage outputs and deterministic control gates.',
      'Evidence IDs reference stored alert evidence such as cited transaction IDs and prior decision IDs; the full ledger remains in the alert detail contract.',
    ],
  }
}

function mockHash(text: string): string {
  let h = 0
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0
  return `sha256:mock-${h.toString(16).padStart(8, '0')}`
}

function mockCopilotLedger(alert: Alert): CopilotRunLedger {
  return {
    runId: 'precomputed-current',
    alertId: alert.alertId,
    mode: 'precomputed',
    provider: 'precomputed-fixture',
    model: alert.triage.model,
    status: 'reconstructed',
    startedAt: alert.triage.generatedAt,
    completedAt: alert.triage.generatedAt,
    latencyMs: 0,
    promptVersion: 'current-source-reconstruction',
    inputSnapshot: {
      alertId: alert.alertId,
      trigger: alert.trigger,
      transactionCount: alert.transactions?.length ?? 0,
      riskScore: alert.riskScore,
      evidenceHash: mockHash(alert.alertId),
    },
    retrieval: {
      candidateCount: 5,
      selectedTypology: alert.triage.matchedTypology,
    },
    llmCalls: [
      {
        stage: 'triageAgent',
        templateId: 'triage-agent-v1',
        model: alert.triage.model,
        responseModel: 'TriageOutput',
        attempt: 1,
        messages: [
          {
            role: 'system',
            content: 'Reconstructed current triage system prompt and candidate typology cards.',
            contentHash: mockHash('triage-agent-v1'),
            redactionLevel: 'piiRedacted',
          },
          {
            role: 'user',
            content: 'Reconstructed prompt envelope from current source templates and stored alert evidence.',
            contentHash: mockHash(alert.alertId),
            redactionLevel: 'piiRedacted',
          },
        ],
        rawResponse: JSON.stringify({
          recommendation: alert.triage.recommendation,
          matchedTypologyCode: alert.triage.matchedTypology.code,
          firedIndicators: alert.triage.indicatorCoverage.fired,
        }),
        rawResponseHash: mockHash(JSON.stringify(alert.triage)),
        schemaValid: true,
        validationError: null,
      },
      {
        stage: 'verifier',
        templateId: 'verifier-v1',
        model: 'deepseek-v4-flash',
        responseModel: 'Verifier',
        attempt: 1,
        messages: [
          {
            role: 'system',
            content: 'Reconstructed current verifier prompt; raw provider prompt was not captured.',
            contentHash: mockHash('verifier-v1'),
            redactionLevel: 'piiRedacted',
          },
        ],
        rawResponse: JSON.stringify(alert.triage.verifier),
        rawResponseHash: mockHash(JSON.stringify(alert.triage.verifier)),
        schemaValid: true,
        validationError: null,
      },
    ],
    deterministicEvents: [
      { stage: 'retrieval', result: 'ranked' },
      { stage: 'screening', result: alert.triage.screening?.status ?? 'unknown' },
      { stage: 'citationGrounding', result: 'grounded' },
      { stage: 'routingPolicy', result: alert.routing ?? 'needsReview' },
    ],
    finalOutput: alert.triage as unknown as Record<string, unknown>,
    redactions: [
      'Precomputed fixture prompts are reconstructed; original raw prompts were not stored.',
      'Evidence content is represented by hash in this reconstructed ledger.',
    ],
    nonClaims: [
      'This ledger exposes the prompt/response envelope VerdictAML controls; it is not DeepSeek chain-of-thought.',
      'Precomputed runs are reconstructed from stored triage outputs and current source templates.',
    ],
  }
}

const MOCK = import.meta.env.VITE_MOCK !== 'false'
const GOVERNANCE_THRESHOLDS = { review: 0.6, autoClear: 0.85, qaSample: 0.2, borderlineMargin: 0.1 }
const MOCK_ACCESS_CONTROL_POSTURE: AccessControlPosture = {
  mode: 'actorRoleHeaders',
  demoFallbackActor: { actorId: 'demo-operator', actorRole: 'admin', source: 'demoFallback' },
  rules: [
    {
      endpoint: '/alerts/{alert_id}/decision',
      method: 'POST',
      allowedRoles: ['analyst', 'compliance', 'admin'],
      control: 'Only an analyst/compliance actor can approve or override the AI recommendation; overrides still require a reason.',
      auditEvent: 'decision',
    },
    {
      endpoint: '/alerts/{alert_id}/str/submit',
      method: 'POST',
      allowedRoles: ['compliance', 'admin'],
      control: 'Filing requires an existing analyst escalation decision plus a compliance-capable actor at submission time.',
      auditEvent: 'submission',
    },
    {
      endpoint: '/alerts/{alert_id}/qa-outcome',
      method: 'POST',
      allowedRoles: ['qa', 'compliance', 'admin'],
      control: 'QA outcomes can only be recorded by QA/compliance actors and are written to the audit trail.',
      auditEvent: 'qaOutcome',
    },
    {
      endpoint: '/governance/change-requests',
      method: 'POST',
      allowedRoles: ['modelRisk', 'compliance', 'security', 'amlOps', 'admin'],
      control: 'Governance changes are recorded as proposed/rejected unless required role approvals are present for approved/applied status.',
      auditEvent: 'governanceChange',
    },
    {
      endpoint: '/reset',
      method: 'POST',
      allowedRoles: ['admin'],
      control: 'Reset is an administrative operation and is blocked for ordinary analyst/QA actors.',
      auditEvent: 'reset',
    },
  ],
  fourEyesControls: [
    'STR submission is separated from the decision endpoint: an escalation decision exists first, then a compliance-capable actor files.',
    'Governance changes with approved/applied status must carry approvals for every required role.',
    'Every protected write records actor id/role either in the returned contract, the audit trail, or both.',
  ],
  nonClaims: [
    'This is not production SSO; it is the authorization seam a bank would bind to OIDC/JWT claims.',
    'The demo fallback actor exists so filmed demos and tests still run without an identity provider.',
    'Role checks do not make synthetic metrics production authorization.',
  ],
}

export interface LearnedPatternRecord {
  signature: string
  typology: string | null
  sourceAlertId: string
  clearedCount: number
  clearedAt: string
}

export interface LearningLoopFutureAlert {
  alertId: string
  holderName: string
  currentRouting?: string | null
  confidence: number
  recommendation: Recommendation
  reason?: string
}

export interface LearningLoopCandidate {
  sourceAlertId: string
  holderName: string
  signature: string | null
  typology: string | null
  recommendation: Recommendation
  verifierStatus: VerifierStatus
  canTeach: boolean
  blockedReason?: string | null
  affectedFutureAlerts: LearningLoopFutureAlert[]
  blockedFutureAlerts: LearningLoopFutureAlert[]
}

export interface LearningLoopOpportunities {
  scannedAlerts: number
  signatureCount: number
  teachableSources: number
  reusableSources: number
  affectedFutureAlerts: number
  candidates: LearningLoopCandidate[]
}
const MOCK_GOVERNANCE_CHANGE_CONTROL: GovernanceChangeRequestList = {
  mode: 'modelRiskChangeControl',
  pending: 2,
  approved: 0,
  blockedReason: 'Runtime config is immutable from the API; changes require explicit approval and deployment.',
  changes: [
    {
      changeId: 'chg-threshold-auto-clear-hardening',
      type: 'thresholdChange',
      status: 'proposed',
      requestedBy: 'model-risk',
      requestedAt: '2026-07-06T10:00:00+08:00',
      currentValue: { review: GOVERNANCE_THRESHOLDS.review, autoClear: GOVERNANCE_THRESHOLDS.autoClear, qaSample: GOVERNANCE_THRESHOLDS.qaSample },
      proposedValue: { autoClear: 0.9, qaSample: 0.3 },
      rationale: 'Raise the auto-clear bar until bank historical replay and QA outcomes prove leakage remains inside tolerance.',
      evidence: ['/governance/validation-dossier', '/metrics', '/qa/outcomes', '/alerts/HERO-002/decision-trace'],
      requiredApprovals: ['compliance', 'modelRisk'],
      approvals: [],
      rollbackPlan: 'Restore previous thresholds, replay the shadow sample, and compare auto-clear leakage plus QA miss rate.',
      nonClaims: ['This proposal does not mutate runtime thresholds.', 'Threshold changes require approval and deployment outside the demo API.'],
    },
    {
      changeId: 'chg-prompt-ledger-versioning',
      type: 'promptTemplate',
      status: 'proposed',
      requestedBy: 'aml-ops',
      requestedAt: '2026-07-06T10:00:00+08:00',
      currentValue: { promptVersion: 'captured-runtime-envelope' },
      proposedValue: { requiredLedgerFields: ['templateId', 'contentHash', 'schemaValid', 'rawResponseHash'] },
      rationale: 'Prevent silent prompt drift by requiring every live copilot run to preserve prompt template ids and response validation evidence.',
      evidence: ['/alerts/HERO-002/copilot-runs/precomputed-current/ledger', '/readiness/summary'],
      requiredApprovals: ['modelRisk', 'security'],
      approvals: [],
      rollbackPlan: 'Revert to the previous prompt template id and compare ledger hashes against the last approved run.',
      nonClaims: ['This record governs prompt transparency; it does not expose DeepSeek chain-of-thought.'],
    },
  ],
}
const MOCK_INTEGRATION_CONTRACT: BankIntegrationContract = {
  mode: 'shadowFirst',
  inboundSystems: ['SAS', 'Actimize', 'Mantas', 'bank rule engine'],
  workflow: [
    {
      title: 'Existing monitoring',
      body: 'SAS / Actimize / Mantas / bank rule engine emits alert id, account, trigger, risk score, and transaction window.',
    },
    {
      title: 'VerdictAML shadow triage',
      body: 'Runs read-only first; triage, verifier, confidence, screening, defense packet, and queue routing are computed without changing the source workflow.',
    },
    {
      title: 'Case-management worklist',
      body: 'needsReview goes to analyst queue; autoCleared remains inspectable, QA-sampled, and logged.',
    },
    {
      title: 'Analyst decision',
      body: 'Human accepts or overrides the AI recommendation. Escalations keep the STR draft; dismissals keep a dismissal record.',
    },
    {
      title: 'goAML filing seam',
      body: 'Approved STR exports as schema-valid goAML XML; filing returns FIU acknowledgement and audit event.',
    },
  ],
  minimumRequiredFields: [
    { name: 'alertId', required: true, source: 'transaction-monitoring system', reason: 'Stable key to reconcile VerdictAML output with the bank case.' },
    { name: 'trigger / originatingRule', required: true, source: 'transaction-monitoring system', reason: 'Explains why the source system generated the alert.' },
    { name: 'riskScore', required: true, source: 'transaction-monitoring system', reason: "Preserves the bank's existing risk signal for queue prioritisation and audit." },
    { name: 'subject account id, type, opening date', required: true, source: 'core banking / case-management system', reason: 'Identifies the reviewed account without needing broad customer PII.' },
    { name: 'transaction id, timestamp, direction, amount, currency', required: true, source: 'ledger / alert transaction window', reason: 'Grounds typology indicators, cited transactions, and STR amounts.' },
    { name: 'counterparty name, account, bank, channel', required: true, source: 'ledger / payment rails', reason: 'Supports counterparty concentration, screening, and money-flow explanation.' },
    { name: 'running balance', required: true, source: 'ledger', reason: 'Supports pass-through and balance-drain evidence without inventing figures.' },
  ],
  optionalEnrichments: [
    { name: 'customer declared occupation / expected activity', required: false, source: 'KYC profile', reason: 'Unlocks KYC-mismatch typologies; absent in public datasets, so it is not fabricated.' },
    { name: 'confirmed STR / no-STR outcome', required: false, source: 'case-management disposition history', reason: 'Needed for bank-specific validation, threshold approval, and override analysis.' },
    { name: 'watchlist match snapshots', required: false, source: 'screening system', reason: "Lets VerdictAML preserve the bank's deterministic sanctions/PEP fail-safe." },
  ],
  outboundArtifacts: ['Analyst worklist routing', 'Defense case JSON', 'goAML XML export', 'FIU filing acknowledgement', 'Append-only audit events'],
  productionGates: [
    'Start read-only on historical alerts.',
    'Compare recommendations against analyst decisions and confirmed STR outcomes.',
    'Compliance signs off thresholds before limited auto-clear.',
    'QA sampling and audit remain always on.',
  ],
  nonGoals: ['Does not replace the source transaction-monitoring detector.', 'Does not auto-file STRs.', 'Does not auto-clear sanctions/PEP hits.'],
}
const MOCK_PRODUCTION_TRUST_PLAN: ProductionTrustPlan = {
  mode: 'productionTrustPlan',
  position: 'VerdictAML does not ask a bank to trust demo auto-clear. It asks for read-only historical replay and a shadow pilot where existing AML alerts prove the data, control, and validation gates before limited automation.',
  targetSystems: [
    'SAS AML / Actimize / Mantas / Oracle FCCM or equivalent source rule engine.',
    'Core banking and KYC profile store.',
    'Ledger, payment rails, channel logs, and running-balance transaction window.',
    'Case-management system for analyst dispositions, overrides, QA, and confirmed STR/no-STR outcomes.',
    'Screening/watchlist service for sanctions, PEP, adverse media, and previous match snapshots.',
    'FIU/goAML filing rail as a human-approved export target.',
  ],
  minimumDataAccess: [
    'Alert id, trigger/rule id, risk score, source system, and created timestamp.',
    'Subject account id, account type, opened date, customer risk rating, and expected activity.',
    'Transaction id, timestamp, direction, amount, currency, channel, counterparty, and running balance.',
    'Screening snapshot for sanctions, PEP, and adverse-media status at decision time.',
    'Historical analyst disposition, QA result, override reason, and confirmed STR/no-STR outcome.',
  ],
  governanceControls: [
    'Auto-clear requires dismiss recommendation, verifier agreement, no screening hit, no adversarial debate, and confidence above threshold.',
    'Every auto-cleared item remains QA-sampled and replayable with evidence, threshold, verifier, screening, and audit provenance.',
    'Analyst override reasons feed governance review; they do not silently change thresholds.',
    'Learned suppression is bounded by provenance, leakage measurement, and network revocation.',
    'STR/goAML export remains blocked until human escalation sign-off and evidence anchoring pass.',
  ],
  validationGates: [
    'Read-only historical replay on bank alerts before live workflow impact.',
    'Compare recommendations against analyst dispositions, QA decisions, and confirmed STR/no-STR outcomes.',
    'Calibrate thresholds against bank-approved leakage tolerance and typology coverage gaps.',
    'Run a shadow pilot where recommendations are visible but production queues and filings remain unchanged.',
    'Model-risk, compliance, security, and rollback sign-off before limited production automation.',
  ],
  items: [
    {
      area: 'integration',
      requirement: 'Show where the product sits in a real AML stack.',
      implementation: 'Post-monitoring, pre-case-handling: consumes existing alerts and returns queue routing, defense cases, QA flags, audit events, and human-gated goAML exports.',
      evidenceEndpoints: ['/integration/contract', '/architecture/technical'],
      productionGate: 'No source detector replacement; pilot starts read-only.',
    },
    {
      area: 'dataAccess',
      requirement: 'State exactly what bank data is required.',
      implementation: 'Minimum access is alert metadata, KYC/account profile, transaction window with running balance, screening snapshot, and historical disposition/outcome labels.',
      evidenceEndpoints: ['/production/trust-plan', '/integration/contract'],
      productionGate: 'No production claim until bank data owners approve field mapping and retention boundaries.',
    },
    {
      area: 'falsePositiveGovernance',
      requirement: 'Govern false positives without creating false clears.',
      implementation: 'Suppression only applies when verifier, screening, debate, threshold, QA, leakage, and revocation controls agree.',
      evidenceEndpoints: ['/governance/validation-dossier', '/queue/briefing'],
      productionGate: 'Suppression starts shadow-only until approved leakage tolerance and QA results pass.',
    },
    {
      area: 'validation',
      requirement: 'Define what must be proven before recommendations are trusted.',
      implementation: 'Historical replay and shadow pilot compare recommendations to analyst dispositions, QA results, and confirmed STR/no-STR outcomes.',
      evidenceEndpoints: ['/metrics', '/governance/validation-dossier', '/pilot/adoption-plan'],
      productionGate: 'Synthetic metrics prove validation machinery, not bank production readiness.',
    },
    {
      area: 'productionGate',
      requirement: 'Prevent unsafe auto-clear or auto-escalation.',
      implementation: 'Consequential actions stay human-gated; readiness verifies every finals contract and rollout requires model-risk, compliance, security, and rollback sign-off.',
      evidenceEndpoints: ['/readiness/summary', '/finals/evidence-bundle'],
      productionGate: 'No autonomous STR filing, no autonomous escalation, no clearing screening hits, no clearing unanchored suspicious activity.',
    },
  ],
  judgeResponse: 'The objection is valid. A bank should not trust our demo to auto-clear production alerts. What we prove now is the integration, data, governance, and validation contract a bank would use to decide whether limited automation is safe after replay and shadow pilot evidence.',
  nonClaims: [
    'Synthetic held-out metrics are not bank-production performance.',
    'No autonomous STR filing or autonomous escalation.',
    'No clearing of sanctions, PEP, adverse-media, debated, or unanchored suspicious-activity cases.',
    'No replacement of SAS AML, Actimize, Mantas, Oracle FCCM, or the bank source detector.',
    'No threshold or suppression change without compliance/model-risk governance.',
  ],
}
const MOCK_PILOT_ADOPTION_PLAN: PilotAdoptionPlan = {
  mode: 'bankPilot',
  targetSegments: [
    'Malaysia/APAC mid-sized banks with high alert queues.',
    'Digital banks and payment providers.',
  ],
  buyerStakeholders: [
    'Head of AML operations',
    'Compliance / MLRO owner',
    'Model risk management',
    'Information security / data protection',
    'Core banking / case-management integration owner',
    'Procurement and legal',
  ],
  pilotEconomics: {
    monthlyAlerts: 5000,
    currentReviewMinutesPerAlert: 12,
    assistedReviewMinutesPerAlert: 7,
    qaSampleMinutesPerAlert: 5,
    estimatedMonthlyHoursSaved: 360,
    valueHypothesis: 'At 5,000 alerts/month, a conservative 5-minute handling reduction on reviewed alerts plus bounded auto-clear can recover hundreds of analyst hours while preserving QA.',
    caveat: 'Pilot economics are a validation target, not a production claim; the bank must replace these assumptions with its own alert volume, salary bands, QA policy, and leakage tolerance.',
  },
  sensitivityCases: [
    { monthlyAlerts: 1000, minutesSavedPerAlert: 3, estimatedMonthlyHoursReturned: 50, caveat: 'Low-volume pilot case.' },
    { monthlyAlerts: 5000, minutesSavedPerAlert: 5, estimatedMonthlyHoursReturned: 417, caveat: 'Mid-market operating case.' },
    { monthlyAlerts: 20000, minutesSavedPerAlert: 8, estimatedMonthlyHoursReturned: 2667, caveat: 'Scale case.' },
  ],
  commercialModel: [
    {
      name: 'Paid shadow pilot',
      customerStage: 'Historical replay and shadow validation',
      pricingModel: 'Fixed pilot fee.',
      includes: ['Validation dossier.'],
      conversionGate: 'Compliance and model-risk owners accept success criteria.',
    },
    {
      name: 'Production assist',
      customerStage: 'Live triage with human-owned decisions',
      pricingModel: 'Annual platform fee plus alert-volume tier.',
      includes: ['Queue triage.'],
      conversionGate: 'Security, legal, and operations sign off.',
    },
    {
      name: 'Governed automation',
      customerStage: 'Limited auto-clear after bank validation',
      pricingModel: 'Enterprise/private deployment tier.',
      includes: ['Approved auto-clear thresholds.'],
      conversionGate: 'Shadow pilot shows acceptable leakage.',
    },
  ],
  competitivePositioning: [
    'VerdictAML is an overlay after existing transaction monitoring, not a replacement for the bank rule engine.',
  ],
  pilotTimeline: [
    { week: 'Weeks 1-2', objective: 'Map fields.', owner: 'IT / security', evidence: '/integration/contract' },
    { week: 'Weeks 3-5', objective: 'Run historical replay.', owner: 'Model risk', evidence: '/governance/validation-dossier' },
    { week: 'Weeks 6-7', objective: 'Run shadow pilot.', owner: 'AML operations', evidence: 'Weekly readiness summaries.' },
    { week: 'Week 8', objective: 'Decide rollout.', owner: 'Compliance / procurement', evidence: 'Business case.' },
  ],
  phases: [
    {
      name: 'Read-only historical replay',
      objective: 'Run VerdictAML on historical alerts without touching the bank workflow.',
      exitCriteria: [
        'Input contract mapped to available bank fields.',
        'Known analyst dispositions and STR/no-STR outcomes loaded for comparison.',
        'No customer-impacting automation enabled.',
      ],
      evidenceProduced: ['Validation dossier on bank data.', 'Threshold recommendation with leakage and QA sampling.'],
    },
    {
      name: 'Security and legal review',
      objective: 'Approve deployment shape, data residency, access controls, and audit obligations.',
      exitCriteria: ['Data processing and retention boundaries documented.', 'Cloud or on-prem LLM path approved.'],
      evidenceProduced: ['Architecture and data-flow diagram.', 'Access-control and audit-log plan.'],
    },
    {
      name: 'Shadow pilot',
      objective: 'Run beside analysts on live alerts while the bank workflow remains authoritative.',
      exitCriteria: ['Override reasons reviewed with compliance.', 'Auto-clear leakage stays within approved tolerance.'],
      evidenceProduced: ['Weekly readiness summaries.', 'Override feedback report.', 'False-clear QA review pack.'],
    },
    {
      name: 'Limited production gate',
      objective: 'Enable only bounded dismiss automation after sign-off.',
      exitCriteria: ['Compliance and model-risk owners approve operating thresholds.', 'Rollback procedure tested.'],
      evidenceProduced: ['Production threshold approval record.', 'Rollback runbook.'],
    },
  ],
  successCriteria: [
    'Recall and leakage measured against bank-known outcomes, not only public synthetic data.',
    'Reduction in analyst review volume without unreviewed sanctions/PEP hits or unanchored STR claims.',
    'Analyst override rate and reasons remain explainable to compliance.',
  ],
  validationEvidence: [
    '/metrics for held-out demo metrics.',
    '/governance/validation-dossier for validation gates and prohibited actions.',
    '/finals/evidence-bundle for a single judge-facing evidence packet.',
    'Bank historical replay report before any production automation.',
  ],
  procurementRisks: [
    'Bank procurement and security review can take months, not days.',
    'Production use needs customer-data agreements, deployment approval, and model-risk sign-off.',
    'Integration effort depends on the bank case-management and transaction-monitoring stack.',
  ],
  nonClaims: [
    'No claim of immediate annual contract after a short pilot.',
    'No claim that synthetic metrics alone authorize production auto-clear.',
    'No unattended STR filing or escalation.',
  ],
}
const MOCK_TECHNICAL_ARCHITECTURE: TechnicalArchitecture = {
  mode: 'technicalArchitecture',
  thesis: 'VerdictAML is an end-to-end AML triage workflow, not a standalone chatbot: bank alerts enter a typed API, agents generate controlled decisions, deterministic gates decide what can leave the queue, and every action is replayable.',
  components: [
    {
      id: 'bank-monitoring',
      name: 'Existing bank monitoring engine',
      layer: 'bank',
      responsibility: 'Emits alert id, trigger, risk score, account, and transaction window.',
      proofEndpoints: ['/integration/contract'],
    },
    {
      id: 'api-store',
      name: 'FastAPI service and relational store',
      layer: 'api',
      responsibility: 'Serves typed contracts and persists alerts, decisions, audit events, and learned patterns.',
      proofEndpoints: ['/health', '/alerts', '/audit'],
    },
    {
      id: 'queue-agent',
      name: 'Queue Agent',
      layer: 'agent',
      responsibility: 'Builds the overnight queue split, QA sample, blocked reasons, and next operating moves.',
      proofEndpoints: ['/queue/briefing', '/operations/impact'],
    },
    {
      id: 'triage-agents',
      name: 'Triage, verifier, screening, and debate agents',
      layer: 'agent',
      responsibility: 'Match typologies, challenge decisions, screen counterparties, and preserve contested calls.',
      proofEndpoints: ['/alerts/HERO-002/defense-case', '/innovation/differentiation'],
    },
    {
      id: 'control-plane',
      name: 'Deterministic control plane',
      layer: 'control',
      responsibility: 'Applies thresholds, verifier gates, screening failsafes, QA sampling, STR gates, and readiness checks.',
      proofEndpoints: ['/governance', '/governance/validation-dossier', '/readiness/summary'],
    },
    {
      id: 'analyst-ui',
      name: 'Analyst and judge dashboard',
      layer: 'ui',
      responsibility: 'Shows queue, evidence, network view, governance, defense artifacts, and judge Q&A.',
      proofEndpoints: ['/finals/evidence-bundle', '/finals/qna-defense'],
    },
  ],
  flows: [
    {
      source: 'bank-monitoring',
      target: 'api-store',
      payload: 'Alert metadata plus ledger transaction window.',
      control: 'Input schema validation rejects malformed alert catalogs before persistence.',
    },
    {
      source: 'api-store',
      target: 'triage-agents',
      payload: 'Account, trigger, transactions, typology cards, screening data, and learned patterns.',
      control: 'LLM output is schema-validated; fallback serves precomputed triage for demo reliability.',
    },
    {
      source: 'triage-agents',
      target: 'control-plane',
      payload: 'Recommendation, confidence, verifier status, screening result, debate, STR draft, and suppression status.',
      control: 'Deterministic gates override model confidence for screening hits, verifier flags, debates, and low confidence.',
    },
    {
      source: 'control-plane',
      target: 'queue-agent',
      payload: 'Routing decision, QA sample flag, blocked reasons, and next operating moves.',
      control: 'Auto-clear is limited to verifier-agreed dismissals above threshold; QA sample remains inspectable.',
    },
    {
      source: 'queue-agent',
      target: 'analyst-ui',
      payload: 'Shift briefing, operational impact, alert queue, defense case, and audit trail.',
      control: 'Human actions write decision events; readiness validates every judge-facing contract.',
    },
  ],
  dataHandling: [
    'Queue list omits embedded transactions; full ledger window loads only on alert detail.',
    'Defense cases cite transaction ids and controls without dumping the full ledger.',
    'Pilot deployment starts read-only on historical alerts before customer-impacting automation.',
  ],
  aiExecution: [
    'Triage agent maps evidence to AML typology indicators and a recommendation.',
    'Verifier agent independently challenges the first-pass decision.',
    'Queue Agent converts per-alert decisions into a shift-level worklist plan.',
  ],
  reliabilityControls: [
    'Typed response models on judge-facing endpoints.',
    'Readiness validates architecture, operations, governance, integration, pilot, innovation, Q&A, and evidence bundle.',
    'Auto-clear is threshold-gated, verifier-gated, screening-gated, QA-sampled, and shadow-only until bank replay.',
    'STR filing is human-gated and evidence-anchored.',
  ],
  demoPath: [
    'Open Operational Impact to state the workflow pain and measured shift effect.',
    'Open Technical Architecture to show the end-to-end flow and controls.',
    'Open Queue Agent briefing and click needsReview / QA sample lanes.',
    'Open Readiness Summary / Evidence Bundle to prove the referenced contracts are live.',
  ],
  caveat: 'This architecture is the finals demo deployment shape. Production deployment must replace demo fixtures with bank historical replay, identity/access controls, customer-data residency, and model-risk signoff.',
}
const MOCK_INNOVATION_DIFFERENTIATION: InnovationDifferentiation = {
  mode: 'evidenceBackedDifferentiation',
  thesis: 'VerdictAML is differentiated by the AML control system around triage: verifier challenge, deterministic gates, network recall, goAML controls, and replayable defense cases.',
  capabilities: [
    {
      name: 'Adversarial verifier and debate',
      genericAlternative: 'Single-pass LLM classification with a persuasive explanation.',
      verdictamlImplementation: 'A verifier challenges triage; contested cases are routed through debate and preserved in defense artifacts.',
      proofEndpoints: ['/alerts/HERO-002/defense-case', '/queue/briefing'],
      defenseValue: 'Shows why a recommendation survived challenge instead of trusting first-pass model confidence.',
      limitation: 'Flagged or consequential decisions still require human judgment.',
    },
    {
      name: 'Mule-network recall layer',
      genericAlternative: 'Review each alert as an isolated transaction-monitoring hit.',
      verdictamlImplementation: 'The network view recovers hidden mule behavior and distinguishes benign neighbors from cluster members.',
      proofEndpoints: ['/alerts/HERO-002/network', '/alerts/HERO-002/defense-case'],
      defenseValue: 'Turns the mule-network differentiator into a concrete demo artifact.',
      limitation: 'Demo network evidence is qualitative until validated on bank graph data.',
    },
    {
      name: 'Human-gated goAML export',
      genericAlternative: 'Generate STR prose and leave filing controls implicit.',
      verdictamlImplementation: 'goAML XML is schema-validated and blocked unless escalation, human sign-off, and anchored STR grounds pass.',
      proofEndpoints: ['/alerts/HERO-002/defense-case', '/integration/contract'],
      defenseValue: 'Makes the filing seam auditable and bounded.',
      limitation: 'Real submission depends on bank/FIU filing rails.',
    },
    {
      name: 'Machine-readable defense case',
      genericAlternative: 'A UI explanation that cannot be independently verified.',
      verdictamlImplementation: 'Each alert exposes evidence, verifier status, auto-clear controls, STR gates, and audit events as a typed contract.',
      proofEndpoints: ['/alerts/HERO-002/defense-case', '/finals/evidence-bundle'],
      defenseValue: 'Lets a reviewer replay why the system cleared, escalated, or blocked action.',
      limitation: 'The packet proves provenance and controls, not bank approval of every judgment.',
    },
    {
      name: 'Shadow-first auto-clear governance',
      genericAlternative: 'Advertise automation percentage as production-ready.',
      verdictamlImplementation: 'Auto-clear is bounded by thresholds, verifier agreement, screening, leakage measurement, QA, and pilot gates.',
      proofEndpoints: ['/governance/validation-dossier', '/pilot/adoption-plan', '/readiness/summary'],
      defenseValue: 'Makes automation conditional and measurable.',
      limitation: 'Production release requires bank historical replay.',
    },
  ],
  nonClaims: [
    'Not novelty by LLM usage alone.',
    'Not claiming autonomous STR filing.',
    'Not claiming production auto-clear from synthetic metrics alone.',
  ],
}
const MOCK_QNA_DEFENSE: FinalsQADefensePacket = {
  mode: 'judgeDefense',
  primaryPosition: 'VerdictAML is built to make AML triage defensible, not to replace compliance judgment.',
  answers: [
    {
      objection: 'Problem relevance: what real AML operations pain does this solve?',
      shortAnswer: 'The operational problem is morning queue overload: show processed alerts, inbox reduction, human-review cases, and analyst time returned.',
      evidenceEndpoints: ['/operations/impact', '/queue/briefing'],
      demoAction: 'Start with Operational Impact, then open the Queue Agent briefing and the needsReview lane.',
      trapToAvoid: 'Do not lead with abstract AI capability before showing the workflow bottleneck.',
    },
    {
      objection: 'Auto-clear safety: what if the system clears a real suspicious case?',
      shortAnswer: 'Auto-clear is threshold-gated, verifier-gated, screening-gated, QA-sampled, and shadow-only until bank replay proves leakage.',
      evidenceEndpoints: ['/governance/validation-dossier', '/alerts/HERO-002/defense-case'],
      demoAction: 'Show leakage, prohibited actions, release gates, and defense-case controls.',
      trapToAvoid: 'Do not say the current clear rate is production-safe.',
    },
    {
      objection: 'Metrics: the recall and precision are modest.',
      shortAnswer: 'The numbers are modest and synthetic; the stronger claim is transparent validation with baseline, confusion matrix, leakage, and gates.',
      evidenceEndpoints: ['/metrics', '/governance/validation-dossier'],
      demoAction: 'Open Metrics, then the validation dossier.',
      trapToAvoid: 'Do not oversell synthetic metrics as bank-production performance.',
    },
    {
      objection: 'Integration: how does this fit a real bank AML stack?',
      shortAnswer: 'VerdictAML sits after existing monitoring and before analyst case handling with an explicit input/output contract.',
      evidenceEndpoints: ['/integration/contract', '/pilot/adoption-plan'],
      demoAction: 'Walk inbound systems, required fields, outbound artifacts, and shadow-first gates.',
      trapToAvoid: 'Do not imply VerdictAML replaces the source detector.',
    },
    {
      objection: 'Production trust: what data, governance, and validation are needed before a bank can trust auto-clear?',
      shortAnswer: 'A bank should not trust demo auto-clear. The production path is existing AML integration, approved alert/KYC/ledger/screening/disposition fields, verifier and QA governance, historical replay, and shadow pilot before limited automation.',
      evidenceEndpoints: ['/production/trust-plan', '/integration/contract', '/governance/validation-dossier', '/pilot/adoption-plan'],
      demoAction: 'Open Production Trust Plan and walk target systems, data access, governance controls, validation gates, and non-claims.',
      trapToAvoid: 'Do not say demo metrics authorize production auto-clear.',
    },
    {
      objection: 'Technical architecture: what exactly runs end to end?',
      shortAnswer: 'Bank monitoring feeds a typed API and store; agents produce recommendations; deterministic controls gate queue routing, QA, STR export, audit, and readiness.',
      evidenceEndpoints: ['/architecture/technical', '/integration/contract', '/readiness/summary'],
      demoAction: 'Open Technical Architecture and walk components, execution flow, data handling, AI execution, and reliability controls.',
      trapToAvoid: 'Do not describe it as a prompt around a dataset.',
    },
    {
      objection: 'Innovation: why is this not just another LLM triage wrapper?',
      shortAnswer: 'The differentiator is the AML control system: verifier, network recall, goAML gate, defense case, and shadow governance.',
      evidenceEndpoints: ['/innovation/differentiation', '/alerts/HERO-002/network', '/alerts/HERO-002/defense-case'],
      demoAction: 'Show innovation differentiation, mule network, and defense case.',
      trapToAvoid: 'Do not claim novelty because it uses an LLM.',
    },
    {
      objection: 'Procurement: bank sales cycles are long.',
      shortAnswer: 'The credible path is historical replay, security/legal review, shadow pilot, then limited production after sign-off. The 5,000-alert/month, 360-hour saving case is a validation target, not a production claim.',
      evidenceEndpoints: ['/pilot/adoption-plan', '/integration/contract'],
      demoAction: 'Open the pilot adoption plan and show pilot economics, procurement risks, and non-claims.',
      trapToAvoid: 'Do not promise immediate annual conversion.',
    },
    {
      objection: 'Live reliability: how do we know the endpoints work?',
      shortAnswer: 'Readiness shape-checks the live contracts behind the pitch before Q&A starts.',
      evidenceEndpoints: ['/readiness/summary', '/finals/evidence-bundle'],
      demoAction: 'Open Defense Artifacts and show readiness passing.',
      trapToAvoid: 'Do not ask judges to trust README links without opening readiness.',
    },
  ],
  closingLine: 'The defensible claim is that VerdictAML exposes the evidence, controls, limits, and validation gates a bank needs before trust.',
}
const MOCK_FINALS_DEMO_SCRIPT: FinalsDemoScript = {
  mode: 'finalsDemo',
  openingLine: 'The operational problem is AML queue overload: remove benign noise without hiding risk or losing auditability.',
  totalMinutes: 7,
  steps: [
    {
      title: 'Start with operational pain',
      timeboxMinutes: 1,
      objective: 'Show queue overload and measured shift-level impact.',
      route: '#/governance',
      action: 'Open Operational Impact and state processed, auto-cleared, human-review, hours returned, and caveat.',
      evidenceEndpoints: ['/operations/impact', '/queue/briefing'],
      judgeTakeaway: 'This is a concrete operations workflow, not a generic chatbot demo.',
      fallback: 'Open /operations/impact directly and read the demoNarrative.',
    },
    {
      title: 'Show the architecture',
      timeboxMinutes: 1,
      objective: 'Prove the system is end-to-end.',
      route: '#/governance',
      action: 'Open Technical Architecture and walk components plus execution flow.',
      evidenceEndpoints: ['/architecture/technical', '/integration/contract'],
      judgeTakeaway: 'Architecture and data handling are explicit, typed, and demo-verifiable.',
      fallback: 'Open /architecture/technical and walk components/flows from JSON.',
    },
    {
      title: 'Operate the Queue Agent',
      timeboxMinutes: 1,
      objective: 'Show automation that preserves human judgment.',
      route: '#/queue',
      action: 'Use Queue Agent next moves; click needsReview and QA sample lanes.',
      evidenceEndpoints: ['/queue/briefing', '/governance/validation-dossier'],
      judgeTakeaway: 'The agent removes noise while contested and consequential cases stay human-gated.',
      fallback: 'Show /queue/briefing and the blockedReasons list.',
    },
    {
      title: 'Open the hero defense case',
      timeboxMinutes: 1.25,
      objective: 'Show explainability, verifier challenge, evidence anchoring, and filing controls.',
      route: '#/alerts/HERO-002',
      action: 'Open HERO-002, then defense case, money flow, network, STR/goAML gate, and audit.',
      evidenceEndpoints: ['/alerts/HERO-002/defense-case', '/alerts/HERO-002/network'],
      judgeTakeaway: 'Every decision is replayable through evidence and controls.',
      fallback: 'Open the defense-case endpoint and focus on controls/audit.',
    },
    {
      title: 'Answer safety and validation',
      timeboxMinutes: 1,
      objective: 'Preempt false-clear and modest-metrics objections.',
      route: '#/governance',
      action: 'Show Validation Dossier: leakage, release gates, prohibited actions, and shadow-only state.',
      evidenceEndpoints: ['/governance/validation-dossier', '/metrics'],
      judgeTakeaway: 'The claim is controlled shadow automation, not production autonomy.',
      fallback: 'Acknowledge modest metrics and point to release gates.',
    },
    {
      title: 'Close with adoption and proof',
      timeboxMinutes: 1.75,
      objective: 'Show commercial realism and verify every referenced endpoint.',
      route: '#/governance',
      action: 'Open Pilot Adoption Plan, Defense Artifacts, Readiness Summary, and Finals Q&A Defense.',
      evidenceEndpoints: ['/pilot/adoption-plan', '/readiness/summary', '/finals/evidence-bundle', '/finals/qna-defense'],
      judgeTakeaway: 'Adoption is bank-realistic and every claim has a live evidence contract.',
      fallback: 'Open /readiness/summary and show every contract passing.',
    },
  ],
  fallbackMoves: [
    'If live LLM/RAG fails, use the precomputed triage path.',
    'If a panel is slow, open the matching endpoint directly and show readiness still passes.',
    'If challenged on metrics, acknowledge modest synthetic performance and pivot to validation gates.',
    'If challenged on production, repeat: shadow-only until bank historical replay and signoff.',
  ],
  closingLine: 'VerdictAML reduces AML queue work while exposing evidence, controls, limits, and the bank validation path.',
  nonClaims: [
    'Do not claim production auto-clear approval from synthetic metrics.',
    'Do not claim autonomous STR filing.',
    'Do not claim VerdictAML replaces the bank source detector.',
    'Do not claim immediate bank procurement conversion.',
  ],
}
const MOCK_READINESS_SUMMARY: ReadinessSummary = {
  status: 'pass',
  checkedAt: '2026-07-06T10:00:00+08:00',
  checks: [
    { name: 'contract /finals/evidence-bundle', endpoint: '/finals/evidence-bundle', ok: true, detail: 'ok' },
    { name: 'contract /metrics', endpoint: '/metrics', ok: true, detail: 'ok' },
    { name: 'contract /governance', endpoint: '/governance', ok: true, detail: 'ok' },
    { name: 'contract /security/access-control', endpoint: '/security/access-control', ok: true, detail: 'ok' },
    { name: 'contract /governance/change-requests', endpoint: '/governance/change-requests', ok: true, detail: 'ok' },
    { name: 'contract /qa/outcomes', endpoint: '/qa/outcomes', ok: true, detail: 'ok' },
    { name: 'contract /queue/briefing', endpoint: '/queue/briefing', ok: true, detail: 'ok' },
    { name: 'contract /alerts/HERO-002/defense-case', endpoint: '/alerts/HERO-002/defense-case', ok: true, detail: 'ok' },
    { name: 'contract /alerts/HERO-002/case-handoff', endpoint: '/alerts/HERO-002/case-handoff', ok: true, detail: 'ok' },
    { name: 'contract /operations/impact', endpoint: '/operations/impact', ok: true, detail: 'ok' },
    { name: 'contract /architecture/technical', endpoint: '/architecture/technical', ok: true, detail: 'ok' },
    { name: 'contract /integration/contract', endpoint: '/integration/contract', ok: true, detail: 'ok' },
    { name: 'contract /production/trust-plan', endpoint: '/production/trust-plan', ok: true, detail: 'ok' },
    { name: 'contract /pilot/adoption-plan', endpoint: '/pilot/adoption-plan', ok: true, detail: 'ok' },
    { name: 'contract /innovation/differentiation', endpoint: '/innovation/differentiation', ok: true, detail: 'ok' },
    { name: 'contract /finals/demo-script', endpoint: '/finals/demo-script', ok: true, detail: 'ok' },
    { name: 'contract /finals/qna-defense', endpoint: '/finals/qna-defense', ok: true, detail: 'ok' },
    { name: 'contract /governance/validation-dossier', endpoint: '/governance/validation-dossier', ok: true, detail: 'ok' },
  ],
}
// Render's `fromService` injects a bare host (e.g. "verdictaml-api.onrender.com"); `new URL(path,
// BASE)` needs an absolute base, so add https:// when no scheme is present. A locally-set
// VITE_API_BASE (with scheme) and the localhost default pass through unchanged.
const RAW_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const BASE = /^https?:\/\//i.test(RAW_BASE) ? RAW_BASE : `https://${RAW_BASE}`

function actorHeaders(actorRole: ActorRole, actorId: string): Record<string, string> {
  return { 'X-Actor-Id': actorId, 'X-Actor-Role': actorRole }
}

export async function getAlerts(status?: AlertStatus): Promise<Alert[]> {
  if (MOCK) {
    const list = mockServedQueueAlerts().map((a) => ({ ...a, transactions: status ? null : a.transactions }))
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
    // Serve-time suppression enrichment + routing, exactly like the backend's enrich_served_alert +
    // route_served_alert (ADR-0021), so the detail's routing agrees with the queue.
    const enriched = { ...alert, triage: { ...alert.triage, suppression: mockSuppress(alert) } }
    return { ...enriched, routing: effectiveRouting(enriched) }
  }
  const r = await fetch(new URL(`/alerts/${alertId}`, BASE))
  if (!r.ok) throw new Error(`GET /alerts/${alertId} ${r.status}`)
  return r.json()
}

export async function getCaseHandoff(alertId: string): Promise<CaseHandoff> {
  if (MOCK) {
    const alert = await getAlert(alertId)
    return mockCaseHandoff(alert)
  }
  const r = await fetch(new URL(`/alerts/${alertId}/case-handoff`, BASE))
  if (!r.ok) throw new Error(`GET /alerts/${alertId}/case-handoff ${r.status}`)
  return r.json()
}

export async function getDecisionTrace(alertId: string): Promise<DecisionTrace> {
  if (MOCK) {
    const alert = await getAlert(alertId)
    return mockDecisionTrace(alert)
  }
  const r = await fetch(new URL(`/alerts/${alertId}/decision-trace`, BASE))
  if (!r.ok) throw new Error(`GET /alerts/${alertId}/decision-trace ${r.status}`)
  return r.json()
}

export async function getCopilotRuns(alertId: string): Promise<CopilotRunList> {
  if (MOCK) {
    const alert = await getAlert(alertId)
    const ledger = mockCopilotLedger(alert)
    return {
      alertId,
      runs: [
        {
          runId: ledger.runId,
          alertId,
          mode: ledger.mode,
          provider: ledger.provider,
          model: ledger.model,
          status: ledger.status,
          startedAt: ledger.startedAt,
          completedAt: ledger.completedAt,
          latencyMs: ledger.latencyMs,
          promptVersion: ledger.promptVersion,
          outputHash: ledger.llmCalls[0].rawResponseHash,
          ledgerEndpoint: `/alerts/${alertId}/copilot-runs/precomputed-current/ledger`,
        },
      ],
    }
  }
  const r = await fetch(new URL(`/alerts/${alertId}/copilot-runs`, BASE))
  if (!r.ok) throw new Error(`GET /alerts/${alertId}/copilot-runs ${r.status}`)
  return r.json()
}

export async function getCopilotRunLedger(alertId: string, runId = 'precomputed-current'): Promise<CopilotRunLedger> {
  if (MOCK) {
    const alert = await getAlert(alertId)
    return mockCopilotLedger(alert)
  }
  const r = await fetch(new URL(`/alerts/${alertId}/copilot-runs/${runId}/ledger`, BASE))
  if (!r.ok) throw new Error(`GET /alerts/${alertId}/copilot-runs/${runId}/ledger ${r.status}`)
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
    const expectedDisposition = finalDispositionFor(triage.recommendation, action)
    if (finalDisposition !== expectedDisposition) {
      throw new Error('finalDisposition must match the stored AI recommendation and requested decision action.')
    }
    const normalizedNote = note?.trim() || null
    if (action === 'override' && normalizedNote == null) {
      throw new Error('Override decisions require an analyst reason in note.')
    }
    mockAudit.push({
      alertId, event: 'decision', at: new Date().toISOString(), action,
      aiRecommendation: triage.recommendation, finalDisposition,
      confidence: triage.confidence, verifierStatus: triage.verifier.status, note: normalizedNote,
      actorId: 'demo-analyst', actorRole: 'analyst',
    })
    mockLearnFromDecision(mockAlerts[idx], finalDisposition)  // Slice A: a dismiss teaches a pattern
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
    headers: { 'Content-Type': 'application/json', ...actorHeaders('analyst', 'demo-analyst') },
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
      submittedAt: new Date().toISOString(), actorId: 'demo-compliance', actorRole: 'compliance',
    }
    mockAudit.push({
      alertId,
      event: 'submission',
      at: ack.submittedAt,
      submissionRef: ack.submissionRef,
      actorId: 'demo-compliance',
      actorRole: 'compliance',
    })
    return ack
  }
  const r = await fetch(new URL(`/alerts/${alertId}/str/submit`, BASE), {
    method: 'POST',
    headers: actorHeaders('compliance', 'demo-compliance'),
  })
  if (!r.ok) throw new Error(`POST /alerts/${alertId}/str/submit ${r.status}`)
  return r.json()
}

export async function getAudit(): Promise<AuditEntry[]> {
  if (MOCK) return [...mockAudit].reverse()
  const r = await fetch(new URL('/audit', BASE))
  if (!r.ok) throw new Error(`GET /audit ${r.status}`)
  return r.json()
}

// Session AI–analyst agreement, computed from the authoritative audit log's decision events
// (so every client agrees). Decision-scoped: autoClear/debateResolved/submission don't count.
export async function getAuditSummary(): Promise<DecisionSummary> {
  if (MOCK) {
    const decisions = mockAudit.filter((e) => e.event === 'decision')
    const approvals = decisions.filter((e) => e.action === 'approve').length
    const n = decisions.length
    return {
      decisions: n,
      approvals,
      overrides: n - approvals,
      agreementRate: n ? Math.round((approvals / n) * 10000) / 10000 : null,
    }
  }
  const r = await fetch(new URL('/audit/summary', BASE))
  if (!r.ok) throw new Error(`GET /audit/summary ${r.status}`)
  return r.json()
}

export async function getMetrics(): Promise<Metrics> {
  if (MOCK) return metricsFixture as Metrics
  const r = await fetch(new URL('/metrics', BASE))
  if (!r.ok) throw new Error(`GET /metrics ${r.status}`)
  return r.json()
}

// Live shift-level workload impact, derived from Queue Agent output and locked review-time metrics.
export async function getOperationalImpact(): Promise<OperationalImpact> {
  if (MOCK) {
    const briefing = await getBriefing()
    const m = metricsFixture as Metrics
    const qaSampleAlerts = briefing.autoCleared ? Math.max(1, Math.round(briefing.autoCleared * GOVERNANCE_THRESHOLDS.qaSample)) : 0
    const baselineReviewMinutes = Math.round(briefing.processed * m.avgReviewTimeBaselineMin * 10) / 10
    const assistedReviewMinutes = Math.round((briefing.needsReview * m.avgReviewTimeWithCopilotMin + qaSampleAlerts * 5) * 10) / 10
    const minutesReturned = Math.max(0, Math.round((baselineReviewMinutes - assistedReviewMinutes) * 10) / 10)
    return {
      mode: 'shiftImpact',
      processedAlerts: briefing.processed,
      autoClearedAlerts: briefing.autoCleared,
      humanReviewAlerts: briefing.needsReview,
      qaSampleAlerts,
      escalationsHeldForSignoff: briefing.escalations,
      verifierFlagged: briefing.flagged,
      baselineReviewMinutes,
      assistedReviewMinutes,
      minutesReturned,
      analystHoursReturned: Math.round((minutesReturned / 60) * 100) / 100,
      queueReductionRate: briefing.processed ? Math.round((briefing.autoCleared / briefing.processed) * 10000) / 10000 : 0,
      reviewFocusMultiplier: Math.round((briefing.processed / Math.max(1, briefing.needsReview)) * 100) / 100,
      assumptions: [
        `Baseline review time uses the locked metric artifact: ${m.avgReviewTimeBaselineMin} minutes per alert.`,
        `Assisted review time uses the locked metric artifact: ${m.avgReviewTimeWithCopilotMin} minutes per human-reviewed alert.`,
        'QA sample effort is modeled at 5 minutes per sampled auto-clear for demo impact only.',
      ],
      controlChecks: [
        'Escalations remain in human review and cannot be auto-filed.',
        'Verifier-flagged, screening-hit, debated, revoked, or low-confidence cases stay in needsReview.',
        'Auto-cleared cases remain inspectable through the cleared lane and QA sample.',
        'Production impact must be remeasured on bank historical replay before release.',
      ],
      demoNarrative: `The operational problem is alert overload: this shift started with ${briefing.processed} alerts. The Queue Agent removed ${briefing.autoCleared} from the analyst inbox, left ${briefing.needsReview} for judgment, and returned about ${(minutesReturned / 60).toFixed(1)} analyst hours while keeping escalations, flagged cases, and QA sampling human-visible.`,
      caveat: 'This is a shift-level demo calculation, not a production ROI claim; a bank pilot must replace the review-time and QA assumptions with its own case data, staffing model, and leakage tolerance.',
    }
  }
  const r = await fetch(new URL('/operations/impact', BASE))
  if (!r.ok) throw new Error(`GET /operations/impact ${r.status}`)
  return r.json()
}

// The held-out evaluation set (250 alerts + ground-truth labels) the accuracy is measured over.
export async function getEvaluation(): Promise<Evaluation | null> {
  if (MOCK) return evaluationFixture as unknown as Evaluation
  const r = await fetch(new URL('/evaluation', BASE))
  if (!r.ok) return null
  return (await r.json()) as Evaluation
}

// Live DeepSeek RAG "what to check" handbook for a typology (retrieve KB passages -> DeepSeek
// writes cited checks). Mock has no backend, so returns null and CoachingPanel falls back to the
// curated card checks; live hits the real /typologies/{code}/handbook endpoint.
export async function getHandbook(code: string): Promise<CoachingHandbook | null> {
  if (MOCK) return null
  try {
    const r = await fetch(new URL(`/typologies/${code}/handbook`, BASE))
    if (!r.ok) return null
    return (await r.json()) as CoachingHandbook
  } catch {
    return null
  }
}

// The precomputed Mule Network for a seed alert (ADR-0009/0015): a real IBM AMLworld fan-in cluster,
// shown qualitatively. Returns null when the alert has no network (most don't) so the reveal simply
// doesn't render — never throws on the expected 404. Mock reads the frozen fixture.
export async function getNetwork(alertId: string): Promise<MuleNetwork | null> {
  if (MOCK) {
    const networks = networksFixture as unknown as Record<string, MuleNetwork>
    return networks[alertId] ?? null
  }
  try {
    const r = await fetch(new URL(`/alerts/${alertId}/network`, BASE))
    if (!r.ok) return null
    return (await r.json()) as MuleNetwork
  } catch {
    return null
  }
}

// Liveness + the active LLM provider (Slice B on-prem swap). Mock reflects the demo's cloud
// DeepSeek default; live reads the backend's real provider (on-prem when OLLAMA_BASE_URL is set).
export async function getHealth(): Promise<Health> {
  if (MOCK) {
    return {
      status: 'ok',
      alertsLoaded: mockAlerts.length,
      transactionsLoaded: mockAlerts.reduce((n, a) => n + (a.transactions?.length ?? 0), 0),
      llmKeyPresent: false,
      model: 'deepseek-v4-pro',
      provider: 'DeepSeek (cloud)',
    }
  }
  const r = await fetch(new URL('/health', BASE))
  if (!r.ok) throw new Error(`GET /health ${r.status}`)
  return r.json()
}

// Model-governance snapshot (ADR-0020): model, thresholds, last validation, override monitoring,
// security posture. Live reads /governance; mock derives from the metrics fixture + config defaults.
export async function getGovernance(): Promise<Governance> {
  if (MOCK) {
    const m = metricsFixture as Metrics
    const decisions = mockAudit.filter((e) => e.event === 'decision')
    const overrides = decisions.filter((e) => e.action === 'override').length
    return {
      model: { workhorse: 'deepseek-v4-pro', verifier: 'deepseek-v4-flash', provider: 'DeepSeek (cloud)' },
      thresholds: GOVERNANCE_THRESHOLDS,
      validation: {
        validatedAt: m.validatedAt ?? null,
        model: m.model ?? null,
        n: m.totalAlerts ?? null,
        recall: m.recall ?? null,
        autoClearLeakageRate: m.autoClearLeakageRate ?? null,
        autoClearPrecision: m.autoClearPrecision ?? null,
        measuredTypologies: m.measuredTypologies ?? [],
        roadmapTypologies: m.roadmapTypologies ?? [],
      },
      override: {
        decisions: decisions.length,
        overrides,
        overrideRate: decisions.length ? Math.round((overrides / decisions.length) * 10000) / 10000 : null,
      },
      securityPosture: [
        'Live API is keyless by design for the demo — an unauthenticated call falls back to precomputed results.',
        'Roadmap: OAuth2/OIDC analyst auth + per-analyst audit attribution, and four-eyes sign-off on STR filing.',
        'Roadmap: PII minimisation — identifiers tokenised before any LLM call; the on-prem model swap keeps data in-bank.',
        'Roadmap: prompt-injection defence — evidence is structured, output schema-validated and figure/citation-anchored.',
      ],
      suppressionFrontier: suppressionFrontierFixture as SuppressionFrontier,
    }
  }
  const r = await fetch(new URL('/governance', BASE))
  if (!r.ok) throw new Error(`GET /governance ${r.status}`)
  return r.json()
}

function mockServedQueueAlerts(): Alert[] {
  // Return alerts from local state, folding in the SAME closed-loop suppression the backend runs
  // (ADR-0021): a matched, envelope-consistent suppression re-routes a borderline dismiss to
  // autoCleared, so dismissing a cluster alert shrinks the needsReview worklist live. Routing is
  // computed BEFORE transactions are nulled for the queue-list contract.
  return mockAlerts.map((a) => {
    const enriched = { ...a, triage: { ...a.triage, suppression: mockSuppress(a) } }
    return { ...enriched, routing: effectiveRouting(enriched) }
  })
}

function mockLearningLoopOpportunities(): LearningLoopOpportunities {
  const bySignature = new Map<string, Alert[]>()
  const signatures = new Map<string, string>()

  for (const alert of mockAlerts) {
    const sig = behavioralSignature(alert)
    if (!sig) continue
    signatures.set(alert.alertId, sig)
    bySignature.set(sig, [...(bySignature.get(sig) ?? []), alert])
  }

  const candidates = mockAlerts.map((alert): LearningLoopCandidate => {
    const triage = alert.triage
    const sig = signatures.get(alert.alertId) ?? null
    const recommendation = triage.recommendation
    const verifierStatus = triage.verifier.status
    const canTeach = sig !== null && recommendation === 'dismiss'
    let blockedReason: string | null = null

    if (sig === null) {
      blockedReason = 'No reusable signature: no matched typology or reusable ledger envelope.'
    } else if (recommendation !== 'dismiss') {
      blockedReason = 'Not a benign-clearance source unless a human overrides to dismiss.'
    } else if (verifierStatus !== 'agreed') {
      blockedReason = 'Verifier contested the call; not a clean precedent.'
    } else if (triage.screening?.blocked) {
      blockedReason = 'Screening block prevents benign memory.'
    }

    const affectedFutureAlerts: LearningLoopFutureAlert[] = []
    const blockedFutureAlerts: LearningLoopFutureAlert[] = []

    if (sig) {
      for (const other of bySignature.get(sig) ?? []) {
        if (other.alertId === alert.alertId) continue

        const otherTriage = other.triage
        const reasons: string[] = []
        if (otherTriage.recommendation !== 'dismiss') reasons.push('future alert is not a dismiss')
        if (otherTriage.verifier.status !== 'agreed') reasons.push('verifier not agreed')
        if (otherTriage.debate) reasons.push('debated alert')
        if (otherTriage.screening?.blocked) reasons.push('screening blocked')
        if (!(otherTriage.confidence >= REVIEW_THRESHOLD && otherTriage.confidence < AUTO_CLEAR_THRESHOLD)) {
          reasons.push('outside learned-suppression confidence band')
        }
        if (!envelopeBenignConsistent(other.transactions)) {
          reasons.push('ledger envelope not benign-consistent')
        }

        const enriched = { ...other, triage: { ...other.triage, suppression: mockSuppress(other) } }
        const item: LearningLoopFutureAlert = {
          alertId: other.alertId,
          holderName: other.account.holderName,
          currentRouting: effectiveRouting(enriched),
          confidence: otherTriage.confidence,
          recommendation: otherTriage.recommendation,
        }
        if (reasons.length) {
          blockedFutureAlerts.push({ ...item, reason: reasons.join('; ') })
        } else {
          affectedFutureAlerts.push(item)
        }
      }
    }

    return {
      sourceAlertId: alert.alertId,
      holderName: alert.account.holderName,
      signature: sig,
      typology: triage.matchedTypology.code,
      recommendation,
      verifierStatus,
      canTeach,
      blockedReason,
      affectedFutureAlerts,
      blockedFutureAlerts,
    }
  })

  const reusable = candidates.filter((c) => c.canTeach && c.affectedFutureAlerts.length > 0)
  return {
    scannedAlerts: mockAlerts.length,
    signatureCount: bySignature.size,
    teachableSources: candidates.filter((c) => c.canTeach).length,
    reusableSources: reusable.length,
    affectedFutureAlerts: reusable.reduce((sum, c) => sum + c.affectedFutureAlerts.length, 0),
    candidates: candidates.sort((a, b) => {
      if (a.affectedFutureAlerts.length !== b.affectedFutureAlerts.length) {
        return b.affectedFutureAlerts.length - a.affectedFutureAlerts.length
      }
      if (a.canTeach !== b.canTeach) return a.canTeach ? -1 : 1
      return a.sourceAlertId.localeCompare(b.sourceAlertId)
    }),
  }
}

export async function getLearnedPatterns(): Promise<LearnedPatternRecord[]> {
  if (MOCK) {
    return Array.from(mockClearedPatterns.values())
      .map(({ signature, typology, sourceAlertId, clearedCount, clearedAt }) => ({
        signature,
        typology,
        sourceAlertId,
        clearedCount,
        clearedAt,
      }))
      .sort((a, b) => b.clearedAt.localeCompare(a.clearedAt))
  }
  const r = await fetch(new URL('/learned-patterns', BASE))
  if (!r.ok) throw new Error(`GET /learned-patterns ${r.status}`)
  return r.json()
}

export async function getLearningLoopOpportunities(): Promise<LearningLoopOpportunities> {
  if (MOCK) return mockLearningLoopOpportunities()
  const r = await fetch(new URL('/learning-loop/opportunities', BASE))
  if (!r.ok) throw new Error(`GET /learning-loop/opportunities ${r.status}`)
  return r.json()
}

export async function getAccessControlPosture(): Promise<AccessControlPosture> {
  if (MOCK) return MOCK_ACCESS_CONTROL_POSTURE
  const r = await fetch(new URL('/security/access-control', BASE))
  if (!r.ok) throw new Error(`GET /security/access-control ${r.status}`)
  return r.json()
}

export async function getGovernanceChangeRequests(): Promise<GovernanceChangeRequestList> {
  if (MOCK) return MOCK_GOVERNANCE_CHANGE_CONTROL
  const r = await fetch(new URL('/governance/change-requests', BASE))
  if (!r.ok) throw new Error(`GET /governance/change-requests ${r.status}`)
  return r.json()
}

export async function getQAOutcomes(): Promise<QAOutcomeSummary> {
  if (MOCK) {
    const reviewed = mockQaOutcomes.length
    const confirmedClears = mockQaOutcomes.filter((o) => o.outcome === 'confirmedClear').length
    const missedSuspicion = mockQaOutcomes.filter((o) => o.outcome === 'missedSuspicion').length
    return {
      reviewed,
      confirmedClears,
      missedSuspicion,
      missRate: reviewed ? Math.round((missedSuspicion / reviewed) * 10000) / 10000 : null,
      outcomes: [...mockQaOutcomes].sort((a, b) => b.reviewedAt.localeCompare(a.reviewedAt)),
    }
  }
  const r = await fetch(new URL('/qa/outcomes', BASE))
  if (!r.ok) throw new Error(`GET /qa/outcomes ${r.status}`)
  return r.json()
}

// Full validation evidence pack (ADR-0020): the number, what baseline means, leakage, and exactly
// what remains prohibited before production release. This is the judge-facing defense artifact.
export async function getValidationDossier(): Promise<ValidationDossier> {
  if (MOCK) {
    const m = metricsFixture as Metrics
    return {
      validatedAt: m.validatedAt ?? null,
      model: m.model ?? null,
      dataset: 'SAML-D held-out report-enriched slice',
      n: m.totalAlerts,
      accuracyVsLabels: m.accuracyVsLabels,
      baselineAccuracy: m.baselineAccuracy,
      baselineExplanation: 'Always-dismiss baseline on this held-out slice: it equals the benign share and catches zero reportable cases.',
      recall: m.recall,
      precision: m.precision,
      specificity: m.specificity,
      confusionMatrix: m.confusionMatrix,
      autoClearedShare: m.autoClearedShare ?? null,
      autoClearPrecision: m.autoClearPrecision ?? null,
      autoClearedReports: m.autoClearedReports ?? null,
      totalReports: m.totalReports ?? null,
      autoClearLeakageRate: m.autoClearLeakageRate ?? null,
      thresholds: GOVERNANCE_THRESHOLDS,
      measuredTypologies: m.measuredTypologies ?? [],
      roadmapTypologies: m.roadmapTypologies ?? [],
      productionState: 'shadowOnly',
      releaseGates: [
        'Historical replay against known analyst decisions and confirmed STR outcomes.',
        'Compliance-approved auto-clear threshold and documented leakage tolerance.',
        'QA sampling remains enabled, with misses feeding threshold rollback.',
        'Typology coverage gaps disclosed before any product claim.',
        'goAML filing remains human-approved and evidence-anchored.',
      ],
      prohibitedActions: [
        'No auto-filing to goAML.',
        'No auto-escalation without analyst approval.',
        'No clearing sanctions/PEP screening hits.',
        'No clearing alerts with unanchored STR grounds.',
      ],
    }
  }
  const r = await fetch(new URL('/governance/validation-dossier', BASE))
  if (!r.ok) throw new Error(`GET /governance/validation-dossier ${r.status}`)
  return r.json()
}

// Bank-facing integration contract: what systems feed VerdictAML, what data is required, and what
// remains out of scope. Live reads the audited API contract; mock uses the same demo payload.
export async function getIntegrationContract(): Promise<BankIntegrationContract> {
  if (MOCK) return MOCK_INTEGRATION_CONTRACT
  const r = await fetch(new URL('/integration/contract', BASE))
  if (!r.ok) throw new Error(`GET /integration/contract ${r.status}`)
  return r.json()
}

// Production trust plan: integration, bank data access, false-positive governance, validation gates.
export async function getProductionTrustPlan(): Promise<ProductionTrustPlan> {
  if (MOCK) return MOCK_PRODUCTION_TRUST_PLAN
  const r = await fetch(new URL('/production/trust-plan', BASE))
  if (!r.ok) throw new Error(`GET /production/trust-plan ${r.status}`)
  return r.json()
}

// Technical architecture contract for the finals architecture/execution rubric.
export async function getTechnicalArchitecture(): Promise<TechnicalArchitecture> {
  if (MOCK) return MOCK_TECHNICAL_ARCHITECTURE
  const r = await fetch(new URL('/architecture/technical', BASE))
  if (!r.ok) throw new Error(`GET /architecture/technical ${r.status}`)
  return r.json()
}

// Conservative bank pilot/procurement plan for the market-adoption defense.
export async function getPilotAdoptionPlan(): Promise<PilotAdoptionPlan> {
  if (MOCK) return MOCK_PILOT_ADOPTION_PLAN
  const r = await fetch(new URL('/pilot/adoption-plan', BASE))
  if (!r.ok) throw new Error(`GET /pilot/adoption-plan ${r.status}`)
  return r.json()
}

// Evidence-backed innovation/differentiation contract for the innovation-score defense.
export async function getInnovationDifferentiation(): Promise<InnovationDifferentiation> {
  if (MOCK) return MOCK_INNOVATION_DIFFERENTIATION
  const r = await fetch(new URL('/innovation/differentiation', BASE))
  if (!r.ok) throw new Error(`GET /innovation/differentiation ${r.status}`)
  return r.json()
}

// Timed finals demo path with evidence endpoints and fallback moves.
export async function getFinalsDemoScript(): Promise<FinalsDemoScript> {
  if (MOCK) return MOCK_FINALS_DEMO_SCRIPT
  const r = await fetch(new URL('/finals/demo-script', BASE))
  if (!r.ok) throw new Error(`GET /finals/demo-script ${r.status}`)
  return r.json()
}

// Prepared finals judge Q&A packet: likely objections mapped to evidence endpoints.
export async function getFinalsQADefense(): Promise<FinalsQADefensePacket> {
  if (MOCK) return MOCK_QNA_DEFENSE
  const r = await fetch(new URL('/finals/qna-defense', BASE))
  if (!r.ok) throw new Error(`GET /finals/qna-defense ${r.status}`)
  return r.json()
}

// In-process backend readiness summary for the finals contracts shown in Governance.
export async function getReadinessSummary(): Promise<ReadinessSummary> {
  if (MOCK) return MOCK_READINESS_SUMMARY
  const r = await fetch(new URL('/readiness/summary', BASE))
  if (!r.ok) throw new Error(`GET /readiness/summary ${r.status}`)
  return r.json()
}

// The Queue Agent's Shift Briefing (ADR-0010) — the overnight-run summary on queue open.
// Mock mode derives it from the fixture routing, mirroring the backend build_shift_briefing.
const BLOCKED_REASON_META: Record<BlockedReason['code'], { label: string; explanation: string }> = {
  escalation: {
    label: 'Escalations to sign',
    explanation: 'Escalation is consequential and can never be auto-cleared or auto-filed.',
  },
  screeningHit: {
    label: 'Screening hits',
    explanation: 'Sanctions or PEP screening matched a counterparty, so the alert stays with a human.',
  },
  adversarialDebate: {
    label: 'Adversarial debate',
    explanation: 'The agents contested the call; contested alerts are firewalled from auto-clear.',
  },
  verifierFlagged: {
    label: 'Verifier flagged',
    explanation: 'The independent verifier challenged the recommendation.',
  },
  revokedSuppression: {
    label: 'Revoked suppressions',
    explanation: 'A learned clearance was cancelled because network evidence made it unsafe.',
  },
  lowConfidenceDismiss: {
    label: 'Low-confidence dismissals',
    explanation: 'The alert was a dismiss, but confidence did not meet the auto-clear bar.',
  },
  other: {
    label: 'Other review',
    explanation: 'The alert stayed in review outside the standard autonomous-clear lanes.',
  },
}

function mockBlockedReasonCode(alert: Alert): BlockedReason['code'] {
  const t = alert.triage
  if (t.recommendation === 'escalate') return 'escalation'
  if (t.screening?.blocked) return 'screeningHit'
  if (t.debate) return 'adversarialDebate'
  if (t.verifier.status === 'flagged') return 'verifierFlagged'
  if (t.suppression?.status === 'revoked') return 'revokedSuppression'
  if (t.recommendation === 'dismiss') return 'lowConfidenceDismiss'
  return 'other'
}

function mockBlockedReasons(alerts: Alert[]): BlockedReason[] {
  const counts = Object.fromEntries(
    Object.keys(BLOCKED_REASON_META).map((code) => [code, 0]),
  ) as Record<BlockedReason['code'], number>
  alerts.filter((a) => a.routing !== 'autoCleared').forEach((a) => {
    counts[mockBlockedReasonCode(a)] += 1
  })
  return (Object.keys(BLOCKED_REASON_META) as BlockedReason['code'][])
    .filter((code) => counts[code] > 0)
    .map((code) => ({
      code,
      label: BLOCKED_REASON_META[code].label,
      count: counts[code],
      explanation: BLOCKED_REASON_META[code].explanation,
    }))
}

function mockNextActions(autoCleared: number, escalations: number, blockedReasons: BlockedReason[]): QueueNextAction[] {
  const actions: QueueNextAction[] = []
  let priority = 1
  if (escalations) {
    actions.push({
      priority: priority++,
      label: 'Sign escalation-ready cases',
      lane: 'needsReview',
      count: escalations,
      rationale: 'Consequential cases stay human-gated; clear these first for filing SLA and compliance review.',
    })
  }
  const challenged = blockedReasons
    .filter((reason) => ['screeningHit', 'adversarialDebate', 'verifierFlagged', 'revokedSuppression'].includes(reason.code))
    .reduce((sum, reason) => sum + reason.count, 0)
  if (challenged) {
    actions.push({
      priority: priority++,
      label: 'Resolve challenged decisions',
      lane: 'needsReview',
      count: challenged,
      rationale: 'Verifier, screening, debate, or network-revocation controls challenged the automation path.',
    })
  }
  const lowConfidence = blockedReasons.find((reason) => reason.code === 'lowConfidenceDismiss')?.count ?? 0
  if (lowConfidence) {
    actions.push({
      priority: priority++,
      label: 'Review low-confidence dismissals',
      lane: 'needsReview',
      count: lowConfidence,
      rationale: 'These are benign-looking alerts that failed the auto-clear confidence bar.',
    })
  }
  if (autoCleared) {
    actions.push({
      priority,
      label: 'Spot-check cleared lane',
      lane: 'qaSample',
      count: autoCleared,
      rationale: 'The agent removed benign noise, but sampled clears remain inspectable for leakage control.',
    })
  }
  return actions.slice(0, 3)
}

export async function getBriefing(): Promise<ShiftBriefing> {
  if (MOCK) {
    const servedAlerts = mockServedQueueAlerts()
    const review = servedAlerts.filter((a) => a.routing !== 'autoCleared')
    const autoCleared = servedAlerts.length - review.length
    const escalations = review.filter((a) => a.triage.recommendation === 'escalate').length
    const flagged = review.filter((a) => a.triage.verifier.status === 'flagged').length
    const blockedReasons = mockBlockedReasons(servedAlerts)
    const nextActions = mockNextActions(autoCleared, escalations, blockedReasons)
    const topBlock = blockedReasons[0]
    const blockedNote = topBlock ? `; top review reason: ${topBlock.label} (${topBlock.count})` : ''
    return {
      generatedAt: QUEUE_AGENT_RUN_AT,
      processed: servedAlerts.length,
      autoCleared,
      needsReview: review.length,
      escalations,
      flagged,
      blockedReasons,
      nextActions,
      summary: `Processed ${servedAlerts.length} alerts overnight. Auto-cleared ${autoCleared} high-confidence benign dismissals; ${review.length} need your review (${escalations} escalations to sign, ${flagged} flagged for judgment${blockedNote}).`,
    }
  }
  const r = await fetch(new URL('/queue/briefing', BASE))
  if (!r.ok) throw new Error(`GET /queue/briefing ${r.status}`)
  return r.json()
}
