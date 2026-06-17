// Wire contract (camelCase) — mirror of backend/schemas.py. Keep in sync.

export type AlertStatus = 'pending' | 'approved' | 'overridden'
export type Direction = 'inbound' | 'outbound'
export type Recommendation = 'escalate' | 'dismiss'
export type VerifierStatus = 'agreed' | 'flagged'
export type DecisionAction = 'approve' | 'override'

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
}

export interface Metrics {
  totalAlerts: number
  accuracyVsLabels: number
  falsePositiveReduction: number
  avgReviewTimeBaselineMin: number
  avgReviewTimeWithCopilotMin: number
}
