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

// A curated typology card (mirror of backend TypologyCard) — the coaching panel reads the
// synced fixture. Only the coaching-relevant fields are used, but the shape mirrors the source.
export interface TypologyCard {
  code: string
  name: string
  source: string
  definition: string
  indicators: string[]
  dataSignals: string[]
  benignLookalike: string
  distinguishingTest: string
  typicalDisposition: string
  strNarrativeHints: string[]
  whatToCheck?: string[]
  // Real regulator red-flag indicators grounding the typology (BNM PD App. 4 / FATF-APG), each
  // with an inline source tag. Shown in the coaching playbook.
  redFlags?: string[]
  citation?: string | null
}

export interface Verifier {
  status: VerifierStatus
  agreesWithRecommendation: boolean
  note?: string | null
  claims?: TracedClaim[]
}

// Adversarial debate (ADR-0011): present only when the verifier's first pass flagged.
export type ReverdictOutcome = 'holds' | 'convinced' | 'conceded'

export interface Challenge {
  counterHypothesis: string
  distinguishingTestAssessment: string
}

export interface Rebuttal {
  argument: string
  conceded: boolean
}

export interface Reverdict {
  outcome: ReverdictOutcome
  dispositionChanged: boolean
  note: string
}

export interface Debate {
  challenge: Challenge
  rebuttal: Rebuttal
  reverdict: Reverdict
}

// Deterministic sanctions/PEP screening (Slice B). status: clear | potential (fuzzy only) |
// hit (an exact/alias match). `blocked` true on any match => fail-safe: never auto-cleared.
export type ScreeningStatus = 'clear' | 'potential' | 'hit'

export interface ScreeningMatch {
  counterpartyId: string
  listName: string
  matchedName: string
  matchType: 'exact' | 'fuzzy'
  score: number
  program?: string | null
}

export interface Screening {
  status: ScreeningStatus
  blocked: boolean
  screenedCounterparties: number
  matches: ScreeningMatch[]
  citation?: string | null
}

// Cross-customer self-learning suppression (Slice A): attached serve-time when an alert matches
// a behavioral-envelope pattern an analyst previously cleared, citing that original decision.
export interface Suppression {
  // 'revoked' (ADR-0021): the Mule Network flagged the cleared counterparty as a Consolidation Account,
  // so the clearance is cancelled and the alert routes to a human — the network policing the memory.
  status: 'suppressed' | 'similar' | 'revoked'
  matchedPatternId: string
  sourceDecisionId: string
  sourceAlertId: string
  signature: string
  clearedCount: number
  clearedAt: string
  rationale: string
  revokedNetworkId?: string | null
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

export interface ClaimEvidence {
  transactionIds: string[]
  firedIndicators: string[]
  matchedTypology?: string | null
  citation?: string | null
}

export interface TracedClaim {
  text: string
  evidence: ClaimEvidence
  anchored: boolean
  // LLM semantic anchor (ADR-0013): a MODEL_VERIFIER judgment of whether the evidence substantiates
  // the claim. Present only on a live /triage?semantic=true run; absent on the deterministic demo path.
  semanticVerdict?: 'supported' | 'unsupported' | 'unclear' | null
  semanticReason?: string | null
}

export interface EvidenceIntegrity {
  anchoredCount: number
  unanchoredCount: number
  totalCount: number
}

export interface NarrativeFigure {
  text: string
  kind: 'transaction' | 'total' | 'balance' | 'unmatched'
  transactionIds: string[]
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
  // Evidence-Anchored STR (ADR-0013): read-only trace. `tracedClaims` = every AI-drafted ground with
  // the evidence it anchors to; `unanchoredClaims` = grounds the self-review pulled from the filed
  // draft (recoverable). Optional so older drafts / the frozen results.json still render.
  tracedClaims?: TracedClaim[] | null
  unanchoredClaims?: string[] | null
  // Every currency amount in the narrative pinned to the exact ledger value it equals, or flagged
  // 'unmatched' (ADR-0013 deepening). Read-only; the prose itself is never pruned.
  narrativeFigures?: NarrativeFigure[] | null
}

export interface TriageResult {
  alertId: string
  recommendation: Recommendation
  confidence: number
  explanation?: string | null
  matchedTypology: MatchedTypology
  citedTransactionIds: string[]
  indicatorCoverage: IndicatorCoverage
  verifier: Verifier
  // Anchored claims replacing free-form prose (ADR-0022): the "why", each self-citing + clamped.
  claims?: TracedClaim[]
  evidenceIntegrity?: EvidenceIntegrity
  // Null unless the verifier's first pass flagged and the two agents debated (ADR-0011).
  debate?: Debate | null
  // Deterministic sanctions/PEP screening (Slice B). Optional: a pre-screening record carries none.
  screening?: Screening | null
  // Cross-customer self-learning suppression (Slice A). Optional: attached serve-time on a match.
  suppression?: Suppression | null
  strDraft: STRDraft | null
  model: string
  generatedAt: string
}

// Account Activity Profile (ADR-0016) — a ledger-derived summary of one alert's window
// (NOT KYC: SAML-D has no customer identity). Attached serve-time to the detail response.
export interface CurrencyFlow {
  currency: string
  inbound: number
  outbound: number
  net: number
}
export interface BalanceSweep {
  opening: number
  peak: number
  low: number
  closing: number
  sweptToNearZero: boolean
}
export interface CrossBorderExposure {
  legs: number
  total: number
  share: number
  jurisdictions: number
}
export interface CashExposure {
  legs: number
  total: number
  share: number
}
export interface Concentration {
  distinctCounterparties: number
  topCounterparty: string | null
  topShare: number
}
export interface AccountActivityProfile {
  turnover: CurrencyFlow[]
  balanceSwept: BalanceSweep
  crossBorder: CrossBorderExposure
  cash: CashExposure
  concentration: Concentration
}

// STR filing-SLA clock (ADR-0016) — the BNM next-working-day deadline, keyed off the
// analyst's escalate decision. Attached serve-time to the detail response.
export type FilingSlaState = 'prospective' | 'active' | 'overdue' | 'notApplicable'
export interface FilingSla {
  applicable: boolean
  state: FilingSlaState
  establishedAt: string | null
  dueBy: string | null
  citation: string
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
  // Serve-time derivations (ADR-0016): ledger-based profile + STR filing-SLA clock. Optional —
  // present only on the detail response, absent on the queue list and the bare live triage.
  activityProfile?: AccountActivityProfile | null
  filingSla?: FilingSla | null
  // Risk-weighted QA sample of the auto-cleared lane (ADR-0019): true when this auto-cleared alert
  // was selected for human spot-check. Marked serve-time on the queue list.
  qaSampled?: boolean | null
  // Borderline dismiss (ADR-0020): a dismiss barely above the review floor or contested — most at
  // risk of a wrong clear. Marked serve-time on the list + detail.
  borderlineDismiss?: boolean | null
}

// GET /typologies/{code}/handbook — live DeepSeek RAG "what to check", each check cited to the
// real KB passage (document + page) it was generated from.
export interface HandbookCheck {
  check: string
  source: string
}
export interface CoachingHandbook {
  typologyCode: string
  whatToCheck: HandbookCheck[]
  sources: string[]
}

// Mule Network (ADR-0009, qualitative per ADR-0015) — GET /alerts/{seedAlertId}/network.
// A real IBM AMLworld fan-in cluster shown illustratively; NO metric is claimed.
export type NetworkRole = 'hub' | 'mule' | 'hidden_mule' | 'benign_cleared' | 'beneficiary'

export interface NetworkNode {
  accountId: string
  holderName: string
  role: NetworkRole
  isSeed: boolean
  x: number
  y: number
  totalLegs?: number | null
  launderingLegs?: number | null
  note?: string | null
}

export interface NetworkEdge {
  fromAccountId: string
  toAccountId: string
  amount: number
  currency: string
  transferCount: number
  laundering: boolean
}

export interface MuleNetwork {
  seedAlertId: string
  typology: MatchedTypology
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  narrative: string
  source: string
  generatedAt: string
}

// GET /health — liveness + the active LLM provider (Slice B on-prem swap).
export interface Health {
  status: string
  alertsLoaded: number
  transactionsLoaded: number
  llmKeyPresent: boolean
  model: string
  provider: string
}

// The Queue Agent's precomputed overnight-run summary (ADR-0010), shown on queue open.
export interface BlockedReason {
  code: 'escalation' | 'screeningHit' | 'adversarialDebate' | 'verifierFlagged' | 'revokedSuppression' | 'lowConfidenceDismiss' | 'other'
  label: string
  count: number
  explanation: string
}

export interface QueueNextAction {
  priority: number
  label: string
  lane: 'needsReview' | 'autoCleared' | 'qaSample'
  count: number
  rationale: string
}

export interface ShiftBriefing {
  generatedAt: string
  processed: number
  autoCleared: number
  needsReview: number
  escalations: number
  flagged: number
  blockedReasons: BlockedReason[]
  nextActions: QueueNextAction[]
  summary: string
}

export interface ConfusionMatrix {
  tp: number
  fp: number
  fn: number
  tn: number
}

// Held-out recall within one true typology on SAML-D (ADR-0012), keyed by card code (+ a
// COVERAGE_GAP bucket). `recall` is null when total is 0.
export interface TypologyRecall {
  recall: number | null
  caught: number
  total: number
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
  // Honest typology coverage of the held-out metric (ADR-0004/0012). Optional: pre-coverage
  // metrics.json predates them.
  measuredTypologies?: string[] | null
  roadmapTypologies?: string[] | null
  coverageNote?: string | null
  // Per-typology held-out recall on SAML-D (ADR-0012), keyed by card code (+ COVERAGE_GAP).
  perTypologyRecall?: Record<string, TypologyRecall> | null
  // Auto-clear false-negative leakage (ADR-0019), derived serve-time & token-free. Optional.
  autoClearedReports?: number | null
  totalReports?: number | null
  autoClearLeakageRate?: number | null
  // Governance validation stamp (ADR-0020): when the held-out eval last ran + the model it used.
  validatedAt?: string | null
  model?: string | null
}

// Model-governance snapshot (ADR-0020) — GET /governance.
export interface GovernanceModel {
  workhorse: string
  verifier: string
  provider: string
}
export interface GovernanceThresholds {
  review: number
  autoClear: number
  qaSample: number
  borderlineMargin: number
}
export interface GovernanceValidation {
  validatedAt: string | null
  model: string | null
  n: number | null
  recall: number | null
  autoClearLeakageRate: number | null
  autoClearPrecision: number | null
  measuredTypologies: string[]
  roadmapTypologies: string[]
}
export interface GovernanceOverride {
  decisions: number
  overrides: number
  overrideRate: number | null
}

export type ActorRole = 'analyst' | 'qa' | 'compliance' | 'modelRisk' | 'amlOps' | 'security' | 'admin'

export interface Actor {
  actorId: string
  actorRole: ActorRole
  source: 'headers' | 'demoFallback'
}

export interface AccessControlRule {
  endpoint: string
  method: 'GET' | 'POST'
  allowedRoles: ActorRole[]
  control: string
  auditEvent: 'decision' | 'submission' | 'qaOutcome' | 'governanceChange' | 'reset' | 'none'
}

export interface AccessControlPosture {
  mode: 'actorRoleHeaders'
  demoFallbackActor: Actor
  rules: AccessControlRule[]
  fourEyesControls: string[]
  nonClaims: string[]
}

export interface GovernanceApproval {
  role: 'compliance' | 'modelRisk' | 'amlOps' | 'security'
  approver: string
  approvedAt: string
  note?: string | null
}

export interface GovernanceChangeRequest {
  changeId: string
  type: 'thresholdChange' | 'suppressionRule' | 'typologyCard' | 'modelProvider' | 'promptTemplate' | 'rollback'
  status: 'proposed' | 'approved' | 'rejected' | 'applied' | 'rolledBack'
  requestedBy: string
  requestedAt: string
  currentValue: Record<string, unknown>
  proposedValue: Record<string, unknown>
  rationale: string
  evidence: string[]
  requiredApprovals: GovernanceApproval['role'][]
  approvals: GovernanceApproval[]
  rollbackPlan: string
  nonClaims: string[]
}

export interface GovernanceChangeRequestList {
  mode: 'modelRiskChangeControl'
  pending: number
  approved: number
  blockedReason?: string | null
  changes: GovernanceChangeRequest[]
}

export interface QAOutcome {
  alertId: string
  outcome: 'confirmedClear' | 'missedSuspicion'
  reviewer: string
  note: string
  reviewedAt: string
  source: 'qaSample' | 'manualReview'
  evidenceEndpoints: string[]
  actorId?: string | null
  actorRole?: ActorRole | null
}

export interface QAOutcomeSummary {
  reviewed: number
  confirmedClears: number
  missedSuspicion: number
  missRate?: number | null
  outcomes: QAOutcome[]
}

// Closed-loop suppression leakage/coverage frontier (ADR-0021): the measured operating point of the
// self-learning auto-suppression. leakage = P(true laundering | auto-suppressed); coverage = share of
// the queue auto-suppressed. ≤1% is aspirational, not certified (see caveat).
export interface SuppressionPoint {
  coverage: number
  leakage: number
  leakage95Upper?: number | null
  suppressed?: number | null
  leaked?: number | null
}
export interface SuppressionFrontier {
  n: number
  nBenign: number
  naive: SuppressionPoint
  operatingPoint: SuppressionPoint
  curve: SuppressionPoint[]
  headline: string
  caveat: string
}
export interface Governance {
  model: GovernanceModel
  thresholds: GovernanceThresholds
  validation: GovernanceValidation
  override: GovernanceOverride
  securityPosture: string[]
  suppressionFrontier?: SuppressionFrontier | null
}

// Validation dossier (GET /governance/validation-dossier): the defensible evidence pack behind
// the headline metrics and the auto-clear safety claim.
export interface ValidationDossier {
  validatedAt: string | null
  model: string | null
  dataset: string
  n: number
  accuracyVsLabels: number
  baselineAccuracy: number
  baselineExplanation: string
  recall: number
  precision: number
  specificity: number
  confusionMatrix: ConfusionMatrix
  autoClearedShare?: number | null
  autoClearPrecision?: number | null
  autoClearedReports?: number | null
  totalReports?: number | null
  autoClearLeakageRate?: number | null
  thresholds: GovernanceThresholds
  measuredTypologies: string[]
  roadmapTypologies: string[]
  productionState: 'shadowOnly'
  releaseGates: string[]
  prohibitedActions: string[]
}

export interface IntegrationStep {
  title: string
  body: string
}

export interface IntegrationDataField {
  name: string
  required: boolean
  source: string
  reason: string
}

export interface BankIntegrationContract {
  mode: 'shadowFirst'
  inboundSystems: string[]
  workflow: IntegrationStep[]
  minimumRequiredFields: IntegrationDataField[]
  optionalEnrichments: IntegrationDataField[]
  outboundArtifacts: string[]
  productionGates: string[]
  nonGoals: string[]
}

export interface ProductionTrustItem {
  area: 'integration' | 'dataAccess' | 'falsePositiveGovernance' | 'validation' | 'productionGate'
  requirement: string
  implementation: string
  evidenceEndpoints: string[]
  productionGate: string
}

export interface ProductionTrustPlan {
  mode: 'productionTrustPlan'
  position: string
  targetSystems: string[]
  minimumDataAccess: string[]
  governanceControls: string[]
  validationGates: string[]
  items: ProductionTrustItem[]
  judgeResponse: string
  nonClaims: string[]
}

export interface ArchitectureComponent {
  id: string
  name: string
  layer: 'bank' | 'api' | 'agent' | 'data' | 'control' | 'ui'
  responsibility: string
  proofEndpoints: string[]
}

export interface ArchitectureFlow {
  source: string
  target: string
  payload: string
  control: string
}

export interface TechnicalArchitecture {
  mode: 'technicalArchitecture'
  thesis: string
  components: ArchitectureComponent[]
  flows: ArchitectureFlow[]
  dataHandling: string[]
  aiExecution: string[]
  reliabilityControls: string[]
  demoPath: string[]
  caveat: string
}

export interface AdoptionPhase {
  name: string
  objective: string
  exitCriteria: string[]
  evidenceProduced: string[]
}

export interface PilotTimelineStep {
  week: string
  objective: string
  owner: string
  evidence: string
}

export interface SensitivityCase {
  monthlyAlerts: number
  minutesSavedPerAlert: number
  estimatedMonthlyHoursReturned: number
  caveat: string
}

export interface CommercialTier {
  name: string
  customerStage: string
  pricingModel: string
  includes: string[]
  conversionGate: string
}

export interface PilotEconomics {
  monthlyAlerts: number
  currentReviewMinutesPerAlert: number
  assistedReviewMinutesPerAlert: number
  qaSampleMinutesPerAlert: number
  estimatedMonthlyHoursSaved: number
  valueHypothesis: string
  caveat: string
}

export interface OperationalImpact {
  mode: 'shiftImpact'
  processedAlerts: number
  autoClearedAlerts: number
  humanReviewAlerts: number
  qaSampleAlerts: number
  escalationsHeldForSignoff: number
  verifierFlagged: number
  baselineReviewMinutes: number
  assistedReviewMinutes: number
  minutesReturned: number
  analystHoursReturned: number
  queueReductionRate: number
  reviewFocusMultiplier: number
  assumptions: string[]
  controlChecks: string[]
  demoNarrative: string
  caveat: string
}

export interface PilotAdoptionPlan {
  mode: 'bankPilot'
  targetSegments: string[]
  buyerStakeholders: string[]
  pilotEconomics: PilotEconomics
  sensitivityCases: SensitivityCase[]
  commercialModel: CommercialTier[]
  competitivePositioning: string[]
  pilotTimeline: PilotTimelineStep[]
  phases: AdoptionPhase[]
  successCriteria: string[]
  validationEvidence: string[]
  procurementRisks: string[]
  nonClaims: string[]
}

export interface DifferentiatedCapability {
  name: string
  genericAlternative: string
  verdictamlImplementation: string
  proofEndpoints: string[]
  defenseValue: string
  limitation: string
}

export interface InnovationDifferentiation {
  mode: 'evidenceBackedDifferentiation'
  thesis: string
  capabilities: DifferentiatedCapability[]
  nonClaims: string[]
}

export interface JudgeDefenseAnswer {
  objection: string
  shortAnswer: string
  evidenceEndpoints: string[]
  demoAction: string
  trapToAvoid: string
}

export interface FinalsDemoStep {
  title: string
  timeboxMinutes: number
  objective: string
  route: string
  action: string
  evidenceEndpoints: string[]
  judgeTakeaway: string
  fallback: string
}

export interface FinalsDemoScript {
  mode: 'finalsDemo'
  openingLine: string
  totalMinutes: number
  steps: FinalsDemoStep[]
  fallbackMoves: string[]
  closingLine: string
  nonClaims: string[]
}

export interface FinalsQADefensePacket {
  mode: 'judgeDefense'
  primaryPosition: string
  answers: JudgeDefenseAnswer[]
  closingLine: string
}

export interface ReadinessCheck {
  name: string
  endpoint: string
  ok: boolean
  detail: string
}

export interface ReadinessSummary {
  status: 'pass' | 'fail'
  checkedAt: string
  checks: ReadinessCheck[]
}

export interface SubmissionAck {
  alertId: string
  submissionRef: string
  status: 'accepted'
  submittedAt: string
  actorId?: string | null
  actorRole?: ActorRole | null
}

export type CaseStatusUpdate = 'needsReview' | 'autoCleared' | 'escalated' | 'dismissed' | 'filed'
export type CaseHandoffWriteBackMode = 'shadowOnly' | 'humanApprovedWriteback'

export interface CaseHandoffDecision {
  aiRecommendation: Recommendation
  confidence: number
  verifierStatus: VerifierStatus
  finalDisposition?: Recommendation | null
  decisionAction?: DecisionAction | null
  overrideReason?: string | null
}

export interface CaseHandoffArtifact {
  name: string
  endpoint: string
  available: boolean
  reason?: string | null
}

export interface CaseHandoffWriteBack {
  mode: CaseHandoffWriteBackMode
  allowed: boolean
  requiresHumanDecision: boolean
  blockedReason?: string | null
  productionGate: string
}

export interface CaseHandoff {
  alertId: string
  generatedAt: string
  sourceSystem: string
  targetSystems: string[]
  caseStatusUpdate: CaseStatusUpdate
  caseNote: string
  decision: CaseHandoffDecision
  attachments: CaseHandoffArtifact[]
  auditEvents: AuditEntry[]
  submissionRef?: string | null
  writeBack: CaseHandoffWriteBack
  nonClaims: string[]
}

export type DecisionTraceStepKind =
  | 'indicatorEvaluation'
  | 'confidenceComputation'
  | 'verifierGate'
  | 'screeningGate'
  | 'debateGate'
  | 'suppressionGate'
  | 'routePolicy'
  | 'strFilingGate'

export interface DecisionTraceStep {
  step: DecisionTraceStepKind
  label: string
  inputs: Record<string, unknown>
  result: string
  evidenceIds: string[]
  deterministic: boolean
}

export interface DecisionTrace {
  alertId: string
  generatedAt: string
  currentRecommendation: Recommendation
  currentConfidence: number
  routing?: Routing | null
  formula: string
  steps: DecisionTraceStep[]
  nonClaims: string[]
}

export interface CopilotLedgerMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
  contentHash: string
  redactionLevel: 'none' | 'piiRedacted'
}

export interface CopilotLedgerLlmCall {
  stage: string
  templateId: string
  model: string
  responseModel: string
  attempt: number
  messages: CopilotLedgerMessage[]
  rawResponse: string
  rawResponseHash: string
  schemaValid: boolean
  validationError?: string | null
}

export interface CopilotRunSummary {
  runId: string
  alertId: string
  mode: 'precomputed' | 'live'
  provider: string
  model: string
  status: 'completed' | 'fallback' | 'failed' | 'reconstructed'
  startedAt: string
  completedAt?: string | null
  latencyMs?: number | null
  promptVersion: string
  outputHash: string
  ledgerEndpoint: string
}

export interface CopilotRunList {
  alertId: string
  runs: CopilotRunSummary[]
}

export interface CopilotRunLedger {
  runId: string
  alertId: string
  mode: 'precomputed' | 'live'
  provider: string
  model: string
  status: 'completed' | 'fallback' | 'failed' | 'reconstructed'
  startedAt: string
  completedAt?: string | null
  latencyMs?: number | null
  promptVersion: string
  inputSnapshot: Record<string, unknown>
  retrieval: Record<string, unknown>
  llmCalls: CopilotLedgerLlmCall[]
  deterministicEvents: Record<string, unknown>[]
  finalOutput: Record<string, unknown>
  redactions: string[]
  nonClaims: string[]
}

// The held-out evaluation SET behind the accuracy number (GET /evaluation): the 250 SAML-D alerts
// the metric is measured on, each with its ground-truth label. `label` is the true outcome — NOT
// the AI's per-alert call (that is the deferred (a) path, one eval re-run).
export interface EvaluationAlert {
  alertId: string
  riskScore: number | null
  txnCount: number
  inCount: number
  outCount: number
  totalAmount: number
  typology: string | null
  coverageGap: boolean
  label: Recommendation
}
export interface Evaluation {
  n: number
  accuracyVsLabels: number | null
  recall: number | null
  precision: number | null
  labelDistribution: { escalate: number; dismiss: number }
  alerts: EvaluationAlert[]
}

export interface AuditEntry {
  alertId: string
  event: 'decision' | 'submission' | 'autoClear' | 'debateResolved' | 'qaOutcome'
  at: string
  action?: DecisionAction | null
  aiRecommendation?: Recommendation | null
  finalDisposition?: Recommendation | null
  confidence?: number | null
  verifierStatus?: VerifierStatus | null
  note?: string | null
  submissionRef?: string | null
  actorId?: string | null
  actorRole?: ActorRole | null
}

// Session, decision-scoped AI–analyst agreement (GET /audit/summary). `agreementRate` is
// null until the first decision — never a misleading 100%. Distinct from Metrics: that is
// held-out AI-vs-ground-truth; this is live AI-vs-human session activity.
export interface DecisionSummary {
  decisions: number
  approvals: number
  overrides: number
  agreementRate: number | null
}
