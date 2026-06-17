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


class Verifier(CamelModel):
    status: Literal["agreed", "flagged"]
    agrees_with_recommendation: bool
    note: str


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


class TriageResult(CamelModel):
    alert_id: str
    recommendation: Literal["escalate", "dismiss"]
    confidence: float
    explanation: str
    matched_typology: MatchedTypology
    cited_transaction_ids: list[str]
    verifier: Verifier
    str_draft: STRDraft | None = None
    model: str
    generated_at: datetime


class Alert(CamelModel):
    alert_id: str
    status: Literal["pending", "approved", "overridden"]
    created_at: datetime
    risk_score: int
    trigger: str
    account: Account
    transaction_ids: list[str]
    triage: TriageResult
    # None in the queue (GET /alerts); populated in detail (GET /alerts/{id}).
    transactions: list[Transaction] | None = None


class Decision(CamelModel):
    alert_id: str
    action: Literal["approve", "override"]
    final_disposition: Literal["escalate", "dismiss"]
    edited_str_draft: STRDraft | None = None
    decided_at: datetime


class Metrics(CamelModel):
    total_alerts: int
    accuracy_vs_labels: float
    false_positive_reduction: float
    avg_review_time_baseline_min: float
    avg_review_time_with_copilot_min: float
