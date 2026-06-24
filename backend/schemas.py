"""API contract models. Internal fields snake_case; wire format camelCase.

This module is the single source of the wire contract (see CLAUDE.md > API contract).
Dump with `by_alias=True` to emit camelCase; models accept either casing on input.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


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


class Verifier(CamelModel):
    status: Literal["agreed", "flagged"]
    agrees_with_recommendation: bool
    note: str


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


class TriageOutput(CamelModel):
    """Internal Triage Agent output. Unlike the wire `TriageResult`, it carries
    `fired_indicators` (consumed by confidence + STR drafting, never serialized)."""
    recommendation: Literal["escalate", "dismiss"]
    matched_typology: MatchedTypology
    fired_indicators: list[str]
    cited_transaction_ids: list[str]
    explanation: str


class TriageResult(CamelModel):
    alert_id: str
    recommendation: Literal["escalate", "dismiss"]
    confidence: float
    explanation: str
    matched_typology: MatchedTypology
    cited_transaction_ids: list[str]
    indicator_coverage: IndicatorCoverage
    verifier: Verifier
    # The adversarial debate (ADR-0011): null unless the Verifier's first pass flagged. Its
    # presence firewalls the alert out of auto-clear (ADR-0010, route_triage).
    debate: Debate | None = None
    str_draft: STRDraft | None = None
    model: str
    generated_at: datetime


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


class Decision(CamelModel):
    alert_id: str
    action: Literal["approve", "override"]
    final_disposition: Literal["escalate", "dismiss"]
    edited_str_draft: STRDraft | None = None
    note: str | None = None  # analyst's reason — captured especially on override
    decided_at: datetime


class AuditEntry(CamelModel):
    """One append-only event in the accountability trail. `event` discriminates:
    a `decision` pairs the AI's call with the human disposition; a `submission`
    records a goAML filing; an `autoClear` records an alert the Queue Agent dismissed
    autonomously, with no human (ADR-0010); a `debateResolved` records an alert that went
    through an adversarial debate (ADR-0011). Fields not relevant to the event are null."""
    alert_id: str
    event: Literal["decision", "submission", "autoClear", "debateResolved"]
    at: datetime
    # decision events
    action: Literal["approve", "override"] | None = None
    ai_recommendation: Literal["escalate", "dismiss"] | None = None
    final_disposition: Literal["escalate", "dismiss"] | None = None
    confidence: float | None = None
    verifier_status: Literal["agreed", "flagged"] | None = None
    note: str | None = None
    # submission events
    submission_ref: str | None = None


class SubmissionAck(CamelModel):
    alert_id: str
    submission_ref: str
    status: Literal["accepted"]
    submitted_at: datetime


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
    summary: str


class ConfusionMatrix(CamelModel):
    """Counts on the held-out eval (positive class = escalate / label Report)."""
    tp: int
    fp: int
    fn: int
    tn: int


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
