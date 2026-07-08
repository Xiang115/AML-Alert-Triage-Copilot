"""API contract models. Internal fields snake_case; wire format camelCase.

This module is the single source of the wire contract (see CLAUDE.md > API contract).
Dump with `by_alias=True` to emit camelCase; models accept either casing on input.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


ActorRole = Literal["analyst", "qa", "compliance", "modelRisk", "amlOps", "security", "admin"]


class Actor(CamelModel):
    actor_id: str
    actor_role: ActorRole
    source: Literal["headers", "demoFallback"] = "headers"


class LLMResponse(BaseModel):
    """Base for the shapes the agents parse out of *untrusted model output*.

    Accepts camelCase (the keys the prompts ask for) and, unlike `CamelModel`,
    *ignores* extra keys: a stray field the model invents should not fail the
    parse — only a missing required field should (that triggers the retry in
    `llm.complete_model`). Required fields are the model's contract; fields with
    defaults are tolerated-if-absent."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class Account(CamelModel):
    account_id: str
    holder_name: str
    account_type: str
    opened_at: datetime


class Transaction(CamelModel):
    transaction_id: str
    timestamp: datetime
    amount: float
    currency: str
    direction: Literal["inbound", "outbound"]
    counterparty_name: str
    counterparty_account: str | None = None
    counterparty_bank: str | None = None
    channel: str
    running_balance: float
    flags: list[str] = []


class MatchedTypology(CamelModel):
    code: str
    name: str
    source: str


class TypologyCard(CamelModel):
    """A curated Typology Card (ADR-0002) — the source-of-truth shape for
    typologies.json and the retrieval unit passed into the Triage/Verifier prompts."""
    code: str
    name: str
    source: str
    definition: str
    indicators: list[str]
    data_signals: list[str]
    benign_lookalike: str
    distinguishing_test: str
    typical_disposition: str
    str_narrative_hints: list[str]
    # Junior-analyst coaching prompts (Slice B): the concrete questions to check before deciding.
    # Optional/additive so an older card still validates. Served to the coaching panel.
    what_to_check: list[str] = []
    # Authoritative red-flag indicators grounding this typology, quoted (lightly trimmed) from
    # real sources — BNM AML/CFT/CPF PD (Feb 2024) Appendix 4, FATF/APG typology reports — each
    # with an inline source tag. Fed to the triage agent as recognition context AND shown in the
    # coaching playbook, so detection and the analyst guidance rest on cited regulator material,
    # not synthesis. Optional/additive.
    red_flags: list[str] = []
    # Section-level regulatory basis surfaced on the STR (Slice B). Optional/additive: a card
    # without one still validates and the STR simply omits the policy line.
    citation: str | None = None


class Verifier(CamelModel):
    status: Literal["agreed", "flagged"]
    agrees_with_recommendation: bool
    note: str | None = None
    claims: list[TracedClaim] = []       # ADR-0022 — the anchored rationale (usually 1–2)


class IndicatorCoverage(CamelModel):
    """The evidence behind `confidence` (ADR-0007): the matched typology's full
    indicator set and the subset that fired for this alert. Serialized so the UI
    can show *why* the score is what it is, rather than a bare percentage. Both
    lists are empty when no typology matched (a reasoned dismiss with no card)."""
    indicators: list[str]
    fired: list[str]


class Period(CamelModel):
    # `from` is a Python keyword, so the field is from_ with an explicit wire alias.
    from_: datetime = Field(alias="from")
    to: datetime


class CitedTransaction(CamelModel):
    transaction_id: str
    timestamp: datetime
    amount: float
    currency: str
    counterparty_name: str
    running_balance: float


class ClaimEvidence(CamelModel):
    """The concrete Anchors an STR grounds-claim traces to (ADR-0013). Every field is
    optional/empty: a claim may anchor to several kinds of evidence, or to none (Unanchored)."""
    transaction_ids: list[str] = []
    fired_indicators: list[str] = []
    matched_typology: str | None = None
    citation: str | None = None


class TracedClaim(CamelModel):
    """One grounds-for-suspicion claim put through Anchoring (ADR-0013): the claim text, the
    evidence it traces to, and whether it anchored. `anchored=True` is an **Anchored Claim**,
    `False` an **Unanchored Claim** — provenance, not proof: an anchor shows the claim *cites* real
    evidence, never that the evidence *substantiates* the suspicion (that judgment stays the
    analyst's, exactly as with Citation Grounding)."""
    text: str
    evidence: ClaimEvidence
    anchored: bool
    # LLM semantic anchor (ADR-0013, OFF the deterministic demo path): a cheap MODEL_VERIFIER
    # judgment of whether the cited evidence actually *substantiates* the claim — catching what the
    # keyword anchor misses (a coincidental match kept, or a real support the keywords didn't see).
    # None on the deterministic path; set only on a semantic-enabled live run.
    semantic_verdict: Literal["supported", "unsupported", "unclear"] | None = None
    semantic_reason: str | None = None


class ClaimCitation(CamelModel):
    """One atomic claim the model emits with the evidence it says it rests on (ADR-0022).
    The pipeline clamps these citations to the real ledger + card before trusting them."""
    text: str
    cited_transaction_ids: list[str] = []
    fired_indicators: list[str] = []


class EvidenceIntegrity(CamelModel):
    """Per-alert provenance summary over the TRIAGE claims (ADR-0022): how many of the AI's
    stated grounds anchor to real evidence vs. are flagged model judgment. Never folded into
    `confidence` — a separate signal."""
    anchored_count: int
    unanchored_count: int
    total_count: int


class NarrativeFigure(CamelModel):
    """A currency amount found in the STR narrative, checked against the ledger (ADR-0013).
    `kind`: 'transaction' (equals a cited transaction's amount), 'total' (equals the sum of the
    cited/alert amounts, incl. the inbound/outbound subtotal), 'balance' (equals a running balance,
    incl. the balance just before a transaction), or 'unmatched' (equals no exact ledger value —
    typically a rounding or a partial subtotal, occasionally a figure worth the analyst's check;
    NOT an accusation of fabrication). Provenance, not proof: a match shows the number exists in the
    ledger, not that the surrounding claim is true."""
    text: str
    kind: Literal["transaction", "total", "balance", "unmatched"]
    transaction_ids: list[str] = []


class STRDraft(CamelModel):
    report_date: datetime
    reporting_institution: str
    subject: Account
    typology: MatchedTypology
    period: Period
    activity_summary: str
    cited_transactions: list[CitedTransaction]
    grounds_for_suspicion: list[str]
    recommended_action: str
    # Evidence-Anchored STR (ADR-0013): additive, read-only trace. `traced_claims` records every
    # AI-drafted ground with the Anchor(s) it traces to and whether it anchored; `unanchored_claims`
    # are the grounds Anchoring pulled from the filed draft (recoverable by the analyst). Optional so
    # older fixtures and the frozen results.json still validate.
    traced_claims: list[TracedClaim] | None = None
    unanchored_claims: list[str] | None = None
    # Every currency amount in the narrative, checked against the ledger (ADR-0013 deepening): each
    # pinned to the specific transaction / total / running-balance it equals, or flagged 'unverified'
    # (matches nothing — the fabricated-figure catch). The prose is never pruned; this is a read-only
    # pre-file figure check over the AI-drafted narrative.
    narrative_figures: list[NarrativeFigure] | None = None


class Challenge(CamelModel):
    """The Verifier's flag stated as an argument (ADR-0011): the counter-hypothesis (the
    benign look-alike) and a point-by-point read of the evidence against the distinguishing
    test. Produced by the un-anchored first pass, so it never sees the Triage explanation."""
    counter_hypothesis: str
    distinguishing_test_assessment: str


class Rebuttal(CamelModel):
    """Triage's single response turn (ADR-0011): defends the call against the Challenge, or
    concedes. `conceded=True` means Triage accepted the challenge — the Disposition flips."""
    argument: str
    conceded: bool


class Reverdict(CamelModel):
    """The Verifier's final judgment after the Rebuttal (ADR-0011). `holds` keeps the flag
    (→ needsReview); `convinced` resolves it (→ agreed, disposition unchanged); `conceded`
    means Triage gave way (→ agreed, disposition flipped). `disposition_changed` records
    whether escalate↔dismiss flipped."""
    outcome: Literal["holds", "convinced", "conceded"]
    disposition_changed: bool
    note: str


class Debate(CamelModel):
    """The recorded adversarial debate (ADR-0011), present on a TriageResult only when the
    Verifier's first pass flagged. Drives the final confidence/routing, is replayed in the
    reasoning timeline, and firewalls the alert out of auto-clear (ADR-0010)."""
    challenge: Challenge
    rebuttal: Rebuttal
    reverdict: Reverdict


class Suppression(CamelModel):
    """Slice A — a cross-customer self-learning suppression citing a prior human clearance.
    Attached to a served TriageResult when the alert's behavioral-envelope signature matches
    a pattern an analyst previously dismissed. `status`: suppressed (auto-clears a borderline dismiss) |
    similar | **revoked** — the Mule Network flagged the cleared counterparty as a Consolidation Account,
    so the clearance is cancelled and the alert routes to a human (Network Revocation, ADR-0021)."""
    status: Literal["suppressed", "similar", "revoked"]
    matched_pattern_id: str
    source_decision_id: str
    source_alert_id: str
    signature: str
    cleared_count: int
    cleared_at: str
    rationale: str
    # Set only when status=="revoked": the Mule Network whose consolidation hub the counterparty is.
    revoked_network_id: str | None = None


class ScreeningMatch(CamelModel):
    """One counterparty matched against a sanctions/PEP watchlist entry. `score` is the
    match strength (1.0 for an exact/alias hit; the token-overlap ratio for a fuzzy one)."""
    counterparty_id: str
    list_name: str  # "OFAC SDN" | "OpenSanctions PEP" | ...
    matched_name: str
    match_type: Literal["exact", "fuzzy"]
    score: float  # 0..1
    program: str | None = None  # sanctions program / PEP role


class Screening(CamelModel):
    """Deterministic sanctions/PEP screening of an alert's counterparties (Slice B). Computed
    once in the pipeline and persisted on the TriageResult; the Auto-Clear Policy reads
    `blocked` as a disqualifier (a hit is never auto-cleared) and the UI reads the same stored
    value, so routing and the panel cannot disagree. `status`: clear (no match) | potential
    (fuzzy only) | hit (an exact/alias match). Always present — a clean screen is the positive
    signal 'screened N, no matches', not an absent field."""
    status: Literal["clear", "potential", "hit"]
    blocked: bool  # true on any match => fail-safe: never auto-clear, force human review
    screened_counterparties: int
    matches: list[ScreeningMatch] = []
    citation: str | None = None  # list source + snapshot


class HandbookCheck(CamelModel):
    """One 'what to check' item in the RAG analyst handbook, cited to the real KB passage it
    was generated from (source document + page)."""
    check: str
    source: str


class CoachingHandbook(CamelModel):
    """Analyst 'what to check' handbook produced by live DeepSeek RAG over the knowledge base
    (agents/coaching): retrieve KB passages -> DeepSeek writes each check ONLY from those passages
    and cites the source page. `sources` lists the distinct documents the checks rest on."""
    typology_code: str
    what_to_check: list[HandbookCheck]
    sources: list[str]


class TriageOutput(CamelModel):
    """Internal Triage Agent output. Unlike the wire `TriageResult`, it carries
    `fired_indicators` (consumed by confidence + STR drafting, never serialized)."""
    recommendation: Literal["escalate", "dismiss"]
    matched_typology: MatchedTypology
    fired_indicators: list[str]
    cited_transaction_ids: list[str]
    claims: list[ClaimCitation] = []


class TriageResult(CamelModel):
    alert_id: str
    recommendation: Literal["escalate", "dismiss"]
    confidence: float
    explanation: str | None = None
    claims: list[TracedClaim] = []       # ADR-0022 — the "why", each self-citing + clamped
    evidence_integrity: EvidenceIntegrity = Field(
        default_factory=lambda: EvidenceIntegrity(anchored_count=0, unanchored_count=0, total_count=0))
    matched_typology: MatchedTypology
    cited_transaction_ids: list[str]
    indicator_coverage: IndicatorCoverage
    verifier: Verifier
    # The adversarial debate (ADR-0011): null unless the Verifier's first pass flagged. Its
    # presence firewalls the alert out of auto-clear (ADR-0010, route_triage).
    debate: Debate | None = None
    # Deterministic sanctions/PEP screening (Slice B). Optional: a pre-screening results.json
    # and any older fixture carry no screening; a hit disqualifies the alert from auto-clear.
    screening: Screening | None = None
    # Cross-customer self-learning suppression (Slice A). Optional: attached serve-time when the
    # alert matches a previously-cleared pattern; A writes this, B never touches it.
    suppression: Suppression | None = None
    str_draft: STRDraft | None = None
    model: str
    generated_at: datetime


class CurrencyFlow(CamelModel):
    """Inbound/outbound/net turnover in one currency over the alert window."""
    currency: str
    inbound: float
    outbound: float
    net: float


class BalanceSweep(CamelModel):
    """The account's balance trajectory across the window. `opening` is the reconstructed
    pre-window balance; `swept_to_near_zero` marks the drains-to-~0 pass-through tell. Reads
    the runningBalance the SAML-D loader reconstructs from real signed flows (label it
    'reconstructed' in the UI)."""
    opening: float
    peak: float
    low: float
    closing: float
    swept_to_near_zero: bool


class CrossBorderExposure(CamelModel):
    """Cross-border legs (rule-flagged, no label leakage) and the count of distinct
    counterparty jurisdictions in the window."""
    legs: int
    total: int
    share: float
    jurisdictions: int


class CashExposure(CamelModel):
    """Cash-channel legs as a share of the window."""
    legs: int
    total: int
    share: float


class Concentration(CamelModel):
    """Counterparty concentration by leg share (well-defined across mixed currencies)."""
    distinct_counterparties: int
    top_counterparty: str | None = None
    top_share: float


class AccountActivityProfile(CamelModel):
    """A ledger-derived summary of one alert's account window (activity_profile.py). NOT KYC:
    SAML-D carries no customer identity, so this summarises what the real ledger shows —
    turnover, balance sweep, cross-border/cash exposure, concentration. Computed serve-time
    and attached to the detail response; never persisted, so it needs no results.json regen."""
    turnover: list[CurrencyFlow]
    balance_swept: BalanceSweep
    cross_border: CrossBorderExposure
    cash: CashExposure
    concentration: Concentration


class FilingSla(CamelModel):
    """The STR filing-SLA clock (sla.py). BNM requires an STR the next working day from when
    the compliance officer establishes suspicion — in the app, the analyst's escalate decision.
    `state`: prospective (pending escalate recommendation — 'if escalated, due by dueBy') |
    active (escalated, clock running) | overdue (past the deadline) | notApplicable (dismissed).
    `due_by` is the deadline date (end of that working day); `established_at` is the decision
    time. Computed serve-time; never persisted."""
    applicable: bool
    state: Literal["prospective", "active", "overdue", "notApplicable"]
    established_at: datetime | None = None
    due_by: date | None = None
    citation: str


class AlertInput(CamelModel):
    """An Alert before triage — the pipeline's input shape. `Alert` is this plus
    the `triage` field, so a stored `Alert` is also a valid `AlertInput`."""
    alert_id: str
    status: Literal["pending", "approved", "overridden"]
    created_at: datetime
    risk_score: int
    trigger: str
    account: Account
    transaction_ids: list[str]
    # None in the queue (GET /alerts); populated in detail (GET /alerts/{id}).
    transactions: list[Transaction] | None = None


class Alert(AlertInput):
    triage: TriageResult
    # The Queue Agent's routing lane (ADR-0010). Optional: a pre-Queue-Agent results.json
    # and the live /triage path (which returns a bare TriageResult) carry no routing.
    routing: Literal["autoCleared", "needsReview"] | None = None
    # Serve-time, read-only derivations attached by GET /alerts/{id} (ADR-0016): the
    # ledger-based Account Activity Profile and the BNM STR filing-SLA clock. Optional —
    # absent on the stored seed, the queue list, and the bare live /triage result.
    activity_profile: AccountActivityProfile | None = None
    filing_sla: FilingSla | None = None
    # Risk-weighted QA sample of the auto-cleared lane (ADR-0019): true when this auto-cleared
    # alert was selected for human spot-check. Marked serve-time on the queue list; absent elsewhere.
    qa_sampled: bool | None = None
    # Borderline dismiss (ADR-0020): a dismiss barely above the review floor or contested — most at
    # risk of a wrong clear. Marked serve-time on the list + detail.
    borderline_dismiss: bool | None = None


class NetworkNode(CamelModel):
    """One account in a Mule Network (ADR-0009, shipped qualitatively per ADR-0015). `role`
    carries the demo story so it drives rendering directly: `hub` = the consolidation account,
    `mule` = a laundering spoke, `hidden_mule` = a spoke account-level triage would dismiss (mostly
    normal activity) but which is a real ring member — the recall reveal, `benign_cleared` = a
    legitimate payer the network clears (discrimination), `beneficiary` = a downstream recipient."""
    account_id: str
    holder_name: str  # real IBM AMLworld entity name (e.g. "Sole Proprietorship #110824")
    role: Literal["hub", "mule", "hidden_mule", "benign_cleared", "beneficiary"]
    is_seed: bool = False  # the account the analyst opened to reveal the network
    # Fixed layout coordinates (ADR-0003 determinism): every render is byte-identical.
    x: float
    y: float
    # The account's individual profile from the real transaction graph — why a hidden mule looks
    # dismissible alone (e.g. total_legs 123, laundering_legs 4 → "3% laundering, reads as normal").
    total_legs: int | None = None
    laundering_legs: int | None = None
    note: str | None = None


class NetworkEdge(CamelModel):
    """One real money-flow edge between two accounts in the network. Derived from actual
    shared-counterparty transactions (no hallucinated edges — ADR-0009); `laundering` is the
    ground-truth label, shown illustratively (ADR-0015)."""
    from_account_id: str
    to_account_id: str
    amount: float
    currency: str
    transfer_count: int
    laundering: bool


class MuleNetwork(CamelModel):
    """A precomputed, frozen Mule Network hero (ADR-0009/0015): ONE real IBM AMLworld fan-in
    cluster, shown QUALITATIVELY — no aggregate metric is claimed (the measured numbers are the
    SAML-D triage metrics, ADR-0012). Structure is assembled deterministically from real edges;
    node roles and the narrative are a precomputed interpretation. Frozen into networks.json and
    served at GET /alerts/{seedAlertId}/network."""
    seed_alert_id: str
    typology: MatchedTypology  # network-scale typology (fan-in consolidation)
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]
    narrative: str
    # Honesty caption carried on the payload so the UI cannot drop it (ADR-0015).
    source: str
    generated_at: datetime


class Decision(CamelModel):
    alert_id: str
    action: Literal["approve", "override"]
    final_disposition: Literal["escalate", "dismiss"]
    edited_str_draft: STRDraft | None = None
    note: str | None = None  # analyst's reason — captured especially on override
    decided_at: datetime
    actor_id: str | None = None
    actor_role: ActorRole | None = None


class AuditEntry(CamelModel):
    """One append-only event in the accountability trail. `event` discriminates:
    a `decision` pairs the AI's call with the human disposition; a `submission`
    records a goAML filing; an `autoClear` records an alert the Queue Agent dismissed
    autonomously, with no human (ADR-0010); a `debateResolved` records an alert that went
    through an adversarial debate (ADR-0011). Fields not relevant to the event are null."""
    alert_id: str
    event: Literal["decision", "submission", "autoClear", "debateResolved", "qaOutcome"]
    at: datetime
    # decision events
    action: Literal["approve", "override"] | None = None
    ai_recommendation: Literal["escalate", "dismiss"] | None = None
    final_disposition: Literal["escalate", "dismiss"] | None = None
    confidence: float | None = None
    verifier_status: Literal["agreed", "flagged"] | None = None
    note: str | None = None
    # access-control attribution
    actor_id: str | None = None
    actor_role: ActorRole | None = None
    # submission events
    submission_ref: str | None = None


class QAOutcome(CamelModel):
    alert_id: str
    outcome: Literal["confirmedClear", "missedSuspicion"]
    reviewer: str
    note: str
    reviewed_at: datetime
    source: Literal["qaSample", "manualReview"] = "qaSample"
    evidence_endpoints: list[str]
    actor_id: str | None = None
    actor_role: ActorRole | None = None


class QAOutcomeRequest(CamelModel):
    outcome: Literal["confirmedClear", "missedSuspicion"]
    reviewer: str = "aml-qa"
    note: str


class QAOutcomeSummary(CamelModel):
    reviewed: int
    confirmed_clears: int
    missed_suspicion: int
    miss_rate: float | None = None
    outcomes: list[QAOutcome]


class DefenseCaseSubject(CamelModel):
    account_id: str
    holder_name: str


class DefenseCaseDecisionContext(CamelModel):
    status: Literal["pending", "approved", "overridden"]
    ai_recommendation: Literal["escalate", "dismiss"]
    confidence: float
    final_disposition: Literal["escalate", "dismiss"] | None = None
    decision_action: Literal["approve", "override"] | None = None


class DefenseCaseStrAnchoring(CamelModel):
    claim_count: int
    traced_claim_count: int
    anchored_claim_count: int
    pulled_unanchored_claim_count: int
    unanchored_claims_still_in_filing: list[str]
    export_blocked: bool


class DefenseCaseEvidence(CamelModel):
    matched_typology: MatchedTypology
    indicator_coverage: IndicatorCoverage
    cited_transaction_ids: list[str]
    str_anchoring: DefenseCaseStrAnchoring | None = None


class DefenseCaseThresholds(CamelModel):
    review: float
    auto_clear: float
    qa_sample: float


class DefenseCaseAutoClearPolicy(CamelModel):
    routing: Literal["autoCleared", "needsReview"] | None = None
    eligible: bool
    thresholds: DefenseCaseThresholds
    qa_sampled: bool
    borderline_dismiss: bool
    reasons: list[str]


class DefenseCaseStrFiling(CamelModel):
    can_file: bool
    requires_escalate_signoff: bool
    blocks_unanchored_grounds: bool
    xsd_validated_on_export: bool


class DefenseCaseControls(CamelModel):
    auto_clear_policy: DefenseCaseAutoClearPolicy
    verifier: Verifier
    screening: Screening | None = None
    debate_present: bool
    str_filing: DefenseCaseStrFiling


class DefenseCase(CamelModel):
    """Machine-readable defense packet for one alert: evidence, controls, and audit."""
    alert_id: str
    generated_at: datetime
    subject: DefenseCaseSubject
    decision_context: DefenseCaseDecisionContext
    evidence: DefenseCaseEvidence
    controls: DefenseCaseControls
    audit: list[AuditEntry]


class CaseHandoffDecision(CamelModel):
    ai_recommendation: Literal["escalate", "dismiss"]
    confidence: float
    verifier_status: Literal["agreed", "flagged"]
    final_disposition: Literal["escalate", "dismiss"] | None = None
    decision_action: Literal["approve", "override"] | None = None
    override_reason: str | None = None


class CaseHandoffArtifact(CamelModel):
    name: str
    endpoint: str
    available: bool
    reason: str | None = None


class CaseHandoffWriteBack(CamelModel):
    mode: Literal["shadowOnly", "humanApprovedWriteback"]
    allowed: bool
    requires_human_decision: bool
    blocked_reason: str | None = None
    production_gate: str


class CaseHandoff(CamelModel):
    """Bank case-management handoff packet: status update, case note, artifacts, and write-back gate."""
    alert_id: str
    generated_at: datetime
    source_system: str
    target_systems: list[str]
    case_status_update: Literal["needsReview", "autoCleared", "escalated", "dismissed", "filed"]
    case_note: str
    decision: CaseHandoffDecision
    attachments: list[CaseHandoffArtifact]
    audit_events: list[AuditEntry]
    submission_ref: str | None = None
    write_back: CaseHandoffWriteBack
    non_claims: list[str]


class DecisionTraceStep(CamelModel):
    step: Literal[
        "indicatorEvaluation",
        "confidenceComputation",
        "verifierGate",
        "screeningGate",
        "debateGate",
        "suppressionGate",
        "routePolicy",
        "strFilingGate",
    ]
    label: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    result: str
    evidence_ids: list[str] = Field(default_factory=list)
    deterministic: bool = True


class DecisionTrace(CamelModel):
    """Observable decision path: stored model outputs plus deterministic control gates."""
    alert_id: str
    generated_at: datetime
    current_recommendation: Literal["escalate", "dismiss"]
    current_confidence: float
    routing: Literal["autoCleared", "needsReview"] | None = None
    formula: str
    steps: list[DecisionTraceStep]
    non_claims: list[str]


class CopilotLedgerMessage(CamelModel):
    role: Literal["system", "user", "assistant"]
    content: str
    content_hash: str
    redaction_level: Literal["none", "piiRedacted"]


class CopilotLedgerLlmCall(CamelModel):
    stage: str
    template_id: str
    model: str
    response_model: str
    attempt: int
    messages: list[CopilotLedgerMessage]
    raw_response: str
    raw_response_hash: str
    schema_valid: bool
    validation_error: str | None = None


class CopilotRunSummary(CamelModel):
    run_id: str
    alert_id: str
    mode: Literal["precomputed", "live"]
    provider: str
    model: str
    status: Literal["completed", "fallback", "failed", "reconstructed"]
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    prompt_version: str
    output_hash: str
    ledger_endpoint: str


class CopilotRunList(CamelModel):
    alert_id: str
    runs: list[CopilotRunSummary]


class CopilotRunLedger(CamelModel):
    run_id: str
    alert_id: str
    mode: Literal["precomputed", "live"]
    provider: str
    model: str
    status: Literal["completed", "fallback", "failed", "reconstructed"]
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    prompt_version: str
    input_snapshot: dict[str, Any]
    retrieval: dict[str, Any]
    llm_calls: list[CopilotLedgerLlmCall]
    deterministic_events: list[dict[str, Any]]
    final_output: dict[str, Any]
    redactions: list[str]
    non_claims: list[str]


class SubmissionAck(CamelModel):
    alert_id: str
    submission_ref: str
    status: Literal["accepted"]
    submitted_at: datetime
    actor_id: str | None = None
    actor_role: ActorRole | None = None


class DecisionSummary(CamelModel):
    """Session, decision-scoped AI–analyst agreement, computed from the audit log's
    `decision` events only (autoClear/debateResolved/submission excluded). `agreementRate`
    is `approvals / decisions`, and `None` until the first decision — never a misleading 100%.
    Authoritative server-side so every client agrees; a session-activity signal, NOT a held-out
    performance metric (that is `Metrics.accuracyVsLabels`)."""
    decisions: int
    approvals: int
    overrides: int
    agreement_rate: float | None = None


class BlockedReason(CamelModel):
    """One disjoint primary reason an alert stayed in needsReview instead of being auto-cleared.

    Counts add up to ShiftBriefing.needs_review; this is the queue-level trust answer, not a
    per-alert defense packet.
    """
    code: Literal[
        "escalation",
        "screeningHit",
        "adversarialDebate",
        "verifierFlagged",
        "revokedSuppression",
        "lowConfidenceDismiss",
        "other",
    ]
    label: str
    count: int
    explanation: str


class QueueNextAction(CamelModel):
    """One prioritized operating move the Queue Agent recommends for the next analyst shift."""
    priority: int
    label: str
    lane: Literal["needsReview", "autoCleared", "qaSample"]
    count: int
    rationale: str


class ShiftBriefing(CamelModel):
    """The Queue Agent's precomputed summary of the overnight run (ADR-0010): the banner
    the analyst sees on arrival. Counts are deterministic; `summary` is a templated
    narrative (LLM-enhanced later). `escalations`/`flagged` are lenses on `needsReview`
    and may overlap."""
    generated_at: datetime
    processed: int
    auto_cleared: int
    needs_review: int
    escalations: int
    flagged: int
    blocked_reasons: list[BlockedReason]
    next_actions: list[QueueNextAction]
    summary: str


class ConfusionMatrix(CamelModel):
    """Counts on the held-out eval (positive class = escalate / label Report)."""
    tp: int
    fp: int
    fn: int
    tn: int


class TypologyRecall(CamelModel):
    """Held-out recall within one true typology (Reports only) on SAML-D (ADR-0012):
    `caught/total`. Keyed by card code (plus a `COVERAGE_GAP` bucket for Reports whose
    pattern maps to no card). `recall` is None when `total` is 0."""
    recall: float | None = None
    caught: int
    total: int


class Metrics(CamelModel):
    total_alerts: int
    accuracy_vs_labels: float
    # Always-dismiss accuracy — the "accuracy is a trap" reference (ADR-0004).
    baseline_accuracy: float
    recall: float  # catch-rate on true Reports = TP/(TP+FN)
    precision: float  # escalate precision = TP/(TP+FP)
    specificity: float  # TN/(TN+FP)
    false_positive_reduction: float
    confusion_matrix: ConfusionMatrix
    avg_review_time_baseline_min: float
    avg_review_time_with_copilot_min: float
    # Queue Agent autonomy outcomes on the held-out slice (ADR-0010). Optional: the
    # pre-Queue-Agent metrics.json predates them and compute_metrics() omits them.
    auto_cleared_share: float | None = None
    auto_clear_precision: float | None = None
    # Honest typology coverage of the held-out metric (ADR-0004): which of the 5 cards this
    # number can actually measure vs those demonstrated on curated data only (SynthAML omits
    # the fields they need). Makes the blended recall an explicit floor over 2 of 5 detectors,
    # not one accuracy figure that hides three data-blind ones. Optional: pre-coverage
    # metrics.json predates them.
    measured_typologies: list[str] | None = None
    roadmap_typologies: list[str] | None = None
    coverage_note: str | None = None
    # Per-typology held-out recall on SAML-D (ADR-0012), keyed by card code (+ a COVERAGE_GAP bucket).
    per_typology_recall: dict[str, TypologyRecall] | None = None
    # Auto-clear false-negative leakage (ADR-0019), derived serve-time & token-free from the locked
    # aggregates above. auto_clear_leakage_rate = P(auto-cleared | true Report) — mix-independent,
    # the honest headline. Optional: a pre-ADR-0019 metrics.json carries none.
    auto_cleared_reports: int | None = None
    total_reports: int | None = None
    auto_clear_leakage_rate: float | None = None
    # Model-governance validation stamp (ADR-0020): when the held-out eval was last run and the
    # model it ran on, so "last validated" is fact-supported, not fabricated. Optional: a
    # pre-ADR-0020 metrics.json predates the stamp.
    validated_at: datetime | None = None
    model: str | None = None


class GovernanceModel(CamelModel):
    workhorse: str
    verifier: str
    provider: str


class GovernanceThresholds(CamelModel):
    review: float
    auto_clear: float
    qa_sample: float
    borderline_margin: float


class GovernanceValidation(CamelModel):
    """The 'last validated' governance stamp (ADR-0020): when the held-out eval last ran and its
    headline numbers. `validated_at`/`model`/`n` come from the eval stamp; the rest from metrics.json."""
    validated_at: datetime | None = None
    model: str | None = None
    n: int | None = None
    recall: float | None = None
    auto_clear_leakage_rate: float | None = None
    auto_clear_precision: float | None = None
    measured_typologies: list[str] = []
    roadmap_typologies: list[str] = []


class GovernanceOverride(CamelModel):
    """Session AI-vs-human override rate from the audit trail (ADR-0020) — a model-monitoring signal."""
    decisions: int
    overrides: int
    override_rate: float | None = None


class GovernanceApproval(CamelModel):
    role: Literal["compliance", "modelRisk", "amlOps", "security"]
    approver: str
    approved_at: datetime
    note: str | None = None


class GovernanceChangeRequest(CamelModel):
    change_id: str
    type: Literal["thresholdChange", "suppressionRule", "typologyCard", "modelProvider", "promptTemplate", "rollback"]
    status: Literal["proposed", "approved", "rejected", "applied", "rolledBack"]
    requested_by: str
    requested_at: datetime
    current_value: dict[str, Any]
    proposed_value: dict[str, Any]
    rationale: str
    evidence: list[str]
    required_approvals: list[Literal["compliance", "modelRisk", "amlOps", "security"]]
    approvals: list[GovernanceApproval] = []
    rollback_plan: str
    non_claims: list[str]


class GovernanceChangeRequestList(CamelModel):
    mode: Literal["modelRiskChangeControl"]
    pending: int
    approved: int
    blocked_reason: str | None = None
    changes: list[GovernanceChangeRequest]


class AccessControlRule(CamelModel):
    endpoint: str
    method: Literal["GET", "POST"]
    allowed_roles: list[ActorRole]
    control: str
    audit_event: Literal["decision", "submission", "qaOutcome", "governanceChange", "reset", "none"]


class AccessControlPosture(CamelModel):
    mode: Literal["actorRoleHeaders"]
    demo_fallback_actor: Actor
    rules: list[AccessControlRule]
    four_eyes_controls: list[str]
    non_claims: list[str]


class SuppressionPoint(CamelModel):
    """One (coverage, leakage) point on the closed-loop suppression frontier (ADR-0021)."""
    coverage: float
    leakage: float
    leakage95_upper: float | None = None
    suppressed: int | None = None
    leaked: int | None = None


class SuppressionFrontier(CamelModel):
    """The measured leakage/coverage frontier of closed-loop suppression (ADR-0021) — the honest
    artifact behind the operating point. `naive` is the coarse-envelope strawman; `operating_point`
    is the pre-registered conservative config; `curve` is the achievable trade-off for the plot.
    Token-free, from `eval/evaluate_suppression.py`; ≤1% is aspirational, not a certified claim."""
    n: int
    n_benign: int
    naive: SuppressionPoint
    operating_point: SuppressionPoint
    curve: list[SuppressionPoint]
    headline: str
    caveat: str


class Governance(CamelModel):
    """Model-governance snapshot (ADR-0020): model + thresholds + last validation + override
    monitoring + a security-posture roadmap. Assembled serve-time from config, metrics, and audit,
    so a model-risk reviewer sees version, operating point, and how the model is monitored."""
    model: GovernanceModel
    thresholds: GovernanceThresholds
    validation: GovernanceValidation
    override: GovernanceOverride
    security_posture: list[str]
    # Closed-loop suppression leakage/coverage frontier (ADR-0021): the measured operating point of
    # the self-learning auto-suppression. Optional — present once eval/evaluate_suppression has run.
    suppression_frontier: SuppressionFrontier | None = None
    # Per-typology held-out recall on SAML-D (ADR-0012), keyed by card code (+ a COVERAGE_GAP
    # bucket): the headline that FI-01/ST-01 — structurally unmeasurable on SynthAML — are the
    # strongest detectors on amount-bearing data. Optional: the SynthAML metrics.json predates it.
    per_typology_recall: dict[str, TypologyRecall] | None = None


class ValidationDossier(CamelModel):
    """Compliance-facing validation dossier for the current operating point."""
    validated_at: datetime | None = None
    model: str | None = None
    dataset: str
    n: int
    accuracy_vs_labels: float
    baseline_accuracy: float
    baseline_explanation: str
    recall: float
    precision: float
    specificity: float
    confusion_matrix: ConfusionMatrix
    auto_cleared_share: float | None = None
    auto_clear_precision: float | None = None
    auto_cleared_reports: int | None = None
    total_reports: int | None = None
    auto_clear_leakage_rate: float | None = None
    thresholds: GovernanceThresholds
    measured_typologies: list[str] = []
    roadmap_typologies: list[str] = []
    production_state: Literal["shadowOnly"]
    release_gates: list[str]
    prohibited_actions: list[str]


class IntegrationStep(CamelModel):
    title: str
    body: str


class IntegrationDataField(CamelModel):
    name: str
    required: bool
    source: str
    reason: str


class BankIntegrationContract(CamelModel):
    """Bank-facing integration contract: required inputs, outputs, and production gates."""
    mode: Literal["shadowFirst"]
    inbound_systems: list[str]
    workflow: list[IntegrationStep]
    minimum_required_fields: list[IntegrationDataField]
    optional_enrichments: list[IntegrationDataField]
    outbound_artifacts: list[str]
    production_gates: list[str]
    non_goals: list[str]


class ProductionTrustItem(CamelModel):
    area: Literal["integration", "dataAccess", "falsePositiveGovernance", "validation", "productionGate"]
    requirement: str
    implementation: str
    evidence_endpoints: list[str]
    production_gate: str


class ProductionTrustPlan(CamelModel):
    """Bank-production trust plan: integration, data access, governance, validation, and non-claims."""
    mode: Literal["productionTrustPlan"]
    position: str
    target_systems: list[str]
    minimum_data_access: list[str]
    governance_controls: list[str]
    validation_gates: list[str]
    items: list[ProductionTrustItem]
    judge_response: str
    non_claims: list[str]


class ArchitectureComponent(CamelModel):
    id: str
    name: str
    layer: Literal["bank", "api", "agent", "data", "control", "ui"]
    responsibility: str
    proof_endpoints: list[str]


class ArchitectureFlow(CamelModel):
    source: str
    target: str
    payload: str
    control: str


class TechnicalArchitecture(CamelModel):
    """Judge-facing technical architecture: components, flows, controls, and demo path."""
    mode: Literal["technicalArchitecture"]
    thesis: str
    components: list[ArchitectureComponent]
    flows: list[ArchitectureFlow]
    data_handling: list[str]
    ai_execution: list[str]
    reliability_controls: list[str]
    demo_path: list[str]
    caveat: str


class AdoptionPhase(CamelModel):
    name: str
    objective: str
    exit_criteria: list[str]
    evidence_produced: list[str]


class PilotTimelineStep(CamelModel):
    week: str
    objective: str
    owner: str
    evidence: str


class SensitivityCase(CamelModel):
    monthly_alerts: int
    minutes_saved_per_alert: int
    estimated_monthly_hours_returned: int
    caveat: str


class CommercialTier(CamelModel):
    name: str
    customer_stage: str
    pricing_model: str
    includes: list[str]
    conversion_gate: str


class PilotEconomics(CamelModel):
    """Conservative commercial-impact assumptions for a bank pilot."""
    monthly_alerts: int
    current_review_minutes_per_alert: int
    assisted_review_minutes_per_alert: int
    qa_sample_minutes_per_alert: int
    estimated_monthly_hours_saved: int
    value_hypothesis: str
    caveat: str


class OperationalImpact(CamelModel):
    """Live shift-level operating impact: workload removed, review effort returned, and controls kept."""
    mode: Literal["shiftImpact"]
    processed_alerts: int
    auto_cleared_alerts: int
    human_review_alerts: int
    qa_sample_alerts: int
    escalations_held_for_signoff: int
    verifier_flagged: int
    baseline_review_minutes: float
    assisted_review_minutes: float
    minutes_returned: float
    analyst_hours_returned: float
    queue_reduction_rate: float
    review_focus_multiplier: float
    assumptions: list[str]
    control_checks: list[str]
    demo_narrative: str
    caveat: str


class PilotAdoptionPlan(CamelModel):
    """Bank-facing pilot/procurement plan: conservative adoption path and evidence required."""
    mode: Literal["bankPilot"]
    target_segments: list[str]
    buyer_stakeholders: list[str]
    pilot_economics: PilotEconomics
    sensitivity_cases: list[SensitivityCase]
    commercial_model: list[CommercialTier]
    competitive_positioning: list[str]
    pilot_timeline: list[PilotTimelineStep]
    phases: list[AdoptionPhase]
    success_criteria: list[str]
    validation_evidence: list[str]
    procurement_risks: list[str]
    non_claims: list[str]


class DifferentiatedCapability(CamelModel):
    name: str
    generic_alternative: str
    verdictaml_implementation: str
    proof_endpoints: list[str]
    defense_value: str
    limitation: str


class InnovationDifferentiation(CamelModel):
    """Evidence-backed differentiators: what is built beyond generic LLM triage."""
    mode: Literal["evidenceBackedDifferentiation"]
    thesis: str
    capabilities: list[DifferentiatedCapability]
    non_claims: list[str]


class JudgeDefenseAnswer(CamelModel):
    objection: str
    short_answer: str
    evidence_endpoints: list[str]
    demo_action: str
    trap_to_avoid: str


class FinalsDemoStep(CamelModel):
    title: str
    timebox_minutes: float
    objective: str
    route: str
    action: str
    evidence_endpoints: list[str]
    judge_takeaway: str
    fallback: str


class FinalsDemoScript(CamelModel):
    """Timed finals demo path with evidence endpoints and fallback moves."""
    mode: Literal["finalsDemo"]
    opening_line: str
    total_minutes: float
    steps: list[FinalsDemoStep]
    fallback_moves: list[str]
    closing_line: str
    non_claims: list[str]


class FinalsQADefensePacket(CamelModel):
    """Prepared finals Q&A answers, each tied to live evidence contracts."""
    mode: Literal["judgeDefense"]
    primary_position: str
    answers: list[JudgeDefenseAnswer]
    closing_line: str


class ReadinessCheck(CamelModel):
    name: str
    endpoint: str
    ok: bool
    detail: str


class ReadinessSummary(CamelModel):
    status: Literal["pass", "fail"]
    checked_at: datetime
    checks: list[ReadinessCheck]


class EvidenceClaim(CamelModel):
    claim: str
    backed_by: list[str]
    caveat: str | None = None


class FinalsEvidenceBundle(CamelModel):
    """Single judge-facing evidence packet for finals claims."""
    generated_at: datetime
    claims: list[EvidenceClaim]
    readiness: ReadinessSummary
    metrics: Metrics
    governance: Governance
    access_control: AccessControlPosture
    governance_change_control: GovernanceChangeRequestList
    qa_outcome_summary: QAOutcomeSummary
    operational_impact: OperationalImpact
    validation_dossier: ValidationDossier
    production_trust_plan: ProductionTrustPlan
    technical_architecture: TechnicalArchitecture
    integration_contract: BankIntegrationContract
    pilot_adoption_plan: PilotAdoptionPlan
    innovation_differentiation: InnovationDifferentiation
    demo_script: FinalsDemoScript
    qna_defense: FinalsQADefensePacket
    hero_defense_case: DefenseCase
    hero_case_handoff: CaseHandoff
    hero_decision_trace: DecisionTrace
    hero_copilot_ledger: CopilotRunLedger
