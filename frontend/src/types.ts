// Wire contract (camelCase) — mirror of backend/schemas.py. Keep in sync.

export type AlertStatus = 'pending' | 'approved' | 'overridden'
export type Direction = 'inbound' | 'outbound'
export type Recommendation = 'escalate' | 'dismiss'
export type VerifierStatus = 'agreed' | 'flagged'
export type DecisionAction = 'approve' | 'override'
// The Queue Agent's routing lane (ADR-0010): an alert it auto-dismissed, or one a human must handle.
export type Routing = 'autoCleared' | 'needsReview'

export interface Account {
  accountId: string
  holderName: string
  accountType: string
  openedAt: string
}

export interface Transaction {
  transactionId: string
  timestamp: string
  amount: number
  currency: string
  direction: Direction
  counterpartyName: string
  counterpartyAccount?: string | null
  counterpartyBank?: string | null
  channel: string
  runningBalance: number
  flags: string[]
}

export interface MatchedTypology {
  code: string
  name: string
  source: string
}

export interface Verifier {
  status: VerifierStatus
  agreesWithRecommendation: boolean
  note: string
}

// The evidence behind `confidence` (ADR-0007): the matched typology's full
// indicator set and the subset that fired. Both empty when no typology matched.
export interface IndicatorCoverage {
  indicators: string[]
  fired: string[]
}

export interface Period {
  from: string
  to: string
}

export interface CitedTransaction {
  transactionId: string
  timestamp: string
  amount: number
  currency: string
  counterpartyName: string
  runningBalance: number
}

export interface STRDraft {
  reportDate: string
  reportingInstitution: string
  subject: Account
  typology: MatchedTypology
  period: Period
  activitySummary: string
  citedTransactions: CitedTransaction[]
  groundsForSuspicion: string[]
  recommendedAction: string
}

export interface TriageResult {
  alertId: string
  recommendation: Recommendation
  confidence: number
  explanation: string
  matchedTypology: MatchedTypology
  citedTransactionIds: string[]
  indicatorCoverage: IndicatorCoverage
  verifier: Verifier
  strDraft: STRDraft | null
  model: string
  generatedAt: string
}

export interface Alert {
  alertId: string
  status: AlertStatus
  createdAt: string
  riskScore: number
  trigger: string
  account: Account
  transactionIds: string[]
  triage: TriageResult
  transactions: Transaction[] | null
  // Queue Agent routing lane (ADR-0010). Optional: a pre-Queue-Agent record carries none.
  routing?: Routing | null
}

// The Queue Agent's precomputed overnight-run summary (ADR-0010), shown on queue open.
export interface ShiftBriefing {
  generatedAt: string
  processed: number
  autoCleared: number
  needsReview: number
  escalations: number
  flagged: number
  summary: string
}

export interface ConfusionMatrix {
  tp: number
  fp: number
  fn: number
  tn: number
}

export interface Metrics {
  totalAlerts: number
  accuracyVsLabels: number
  baselineAccuracy: number
  recall: number
  precision: number
  specificity: number
  falsePositiveReduction: number
  confusionMatrix: ConfusionMatrix
  avgReviewTimeBaselineMin: number
  avgReviewTimeWithCopilotMin: number
  // Queue Agent autonomy on the held-out slice (ADR-0010). Optional: a pre-Queue-Agent
  // metrics.json predates them.
  autoClearedShare?: number | null
  autoClearPrecision?: number | null
}

export interface SubmissionAck {
  alertId: string
  submissionRef: string
  status: 'accepted'
  submittedAt: string
}

export interface AuditEntry {
  alertId: string
  event: 'decision' | 'submission' | 'autoClear'
  at: string
  action?: DecisionAction | null
  aiRecommendation?: Recommendation | null
  finalDisposition?: Recommendation | null
  confidence?: number | null
  verifierStatus?: VerifierStatus | null
  note?: string | null
  submissionRef?: string | null
}
