"""STR drafter (ADR-0006): a structured STRDraft object, only on escalate.

The model writes the two editable narrative fields (activitySummary,
groundsForSuspicion); everything else is assembled deterministically from the
alert + matched typology, so the structured report can't be hallucinated.
"""

from __future__ import annotations

from datetime import datetime

import config
from llm import complete_model
from schemas import (
    AlertInput,
    CitedTransaction,
    LLMResponse,
    Period,
    STRDraft,
    TriageOutput,
    TypologyCard,
)

_REPORTING_INSTITUTION = "Demo Bank Berhad"

_SYSTEM = (
    "You are drafting a Suspicious Transaction Report for an AML analyst. Write only the narrative. "
    'Reply ONLY with JSON: {"activitySummary" (2-3 sentence plain-English account of the activity), '
    '"groundsForSuspicion" (list of short bullet strings)}.'
)


class _StrNarrative(LLMResponse):
    """The two editable narrative fields the model writes (ADR-0006). Both required:
    a draft missing either is incomplete and should trigger the retry."""

    activity_summary: str
    grounds_for_suspicion: list[str]


def _cited(alert: AlertInput, ids: list[str]) -> list[CitedTransaction]:
    by_id = {t.transaction_id: t for t in (alert.transactions or [])}
    out = []
    for tid in ids:
        t = by_id.get(tid)
        if t:
            out.append(
                CitedTransaction(
                    transaction_id=t.transaction_id,
                    timestamp=t.timestamp,
                    amount=t.amount,
                    currency=t.currency,
                    counterparty_name=t.counterparty_name,
                    running_balance=t.running_balance,
                )
            )
    return out


def draft_str(alert: AlertInput, triage_result: TriageOutput, card: TypologyCard, *, client=None,
              model: str | None = None) -> STRDraft | None:
    if triage_result.recommendation != "escalate":
        return None

    cited = _cited(alert, triage_result.cited_transaction_ids)
    txn_lines = "\n".join(
        f"  {t.transaction_id} | {t.timestamp} | {t.amount} {t.currency} | "
        f"{t.counterparty_name} | runningBalance {t.running_balance}"
        for t in cited
    )

    narrative = complete_model(
        _SYSTEM,
        f"Typology: {triage_result.matched_typology.name}\n"
        f"Indicators present: {triage_result.fired_indicators}\n"
        f"Triage explanation: {triage_result.explanation}\n"
        f"Account holder: {alert.account.holder_name}\n"
        f"Cited transactions (id | time | amount | counterparty | runningBalance):\n{txn_lines}\n"
        f"Narrative hints: {card.str_narrative_hints}",
        model or config.MODEL_WORKHORSE,
        _StrNarrative,
        client=client,
        max_tokens=3000,  # STR narrative is longer; leave room over reasoning tokens
    )

    times = [t.timestamp for t in cited] or [datetime.now()]
    return STRDraft(
        report_date=datetime.now(),
        reporting_institution=_REPORTING_INSTITUTION,
        subject=alert.account,
        typology=triage_result.matched_typology,
        period=Period(**{"from": min(times), "to": max(times)}),
        activity_summary=narrative.activity_summary,
        cited_transactions=cited,
        grounds_for_suspicion=narrative.grounds_for_suspicion,
        recommended_action="Escalate to the Financial Intelligence and Enforcement Department (FIED).",
    )
