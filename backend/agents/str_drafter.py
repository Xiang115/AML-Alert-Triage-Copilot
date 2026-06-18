"""STR drafter (ADR-0006): a structured STRDraft object, only on escalate.

The model writes the two editable narrative fields (activitySummary,
groundsForSuspicion); everything else is assembled deterministically from the
alert + matched typology, so the structured report can't be hallucinated.
"""

from __future__ import annotations

from datetime import datetime

import config
from llm import complete_json

_REPORTING_INSTITUTION = "Demo Bank Berhad"

_SYSTEM = (
    "You are drafting a Suspicious Transaction Report for an AML analyst. Write only the narrative. "
    'Reply ONLY with JSON: {"activitySummary" (2-3 sentence plain-English account of the activity), '
    '"groundsForSuspicion" (list of short bullet strings)}.'
)


def _cited(alert: dict, ids: list[str]) -> list[dict]:
    by_id = {t["transactionId"]: t for t in (alert.get("transactions") or [])}
    out = []
    for tid in ids:
        t = by_id.get(tid)
        if t:
            out.append(
                {
                    "transactionId": t["transactionId"],
                    "timestamp": t["timestamp"],
                    "amount": t["amount"],
                    "currency": t["currency"],
                    "counterpartyName": t["counterpartyName"],
                    "runningBalance": t["runningBalance"],
                }
            )
    return out


def draft_str(alert: dict, triage_result: dict, card: dict, *, client=None, model: str | None = None) -> dict | None:
    if triage_result["recommendation"] != "escalate":
        return None

    raw = complete_json(
        _SYSTEM,
        f"Typology: {triage_result['matchedTypology']['name']}\n"
        f"Indicators present: {triage_result['firedIndicators']}\n"
        f"Triage explanation: {triage_result['explanation']}\n"
        f"Account holder: {alert['account']['holderName']}",
        model or config.MODEL_WORKHORSE,
        client=client,
        max_tokens=3000,  # STR narrative is longer; leave room over reasoning tokens
    )

    cited = _cited(alert, triage_result["citedTransactionIds"])
    times = [t["timestamp"] for t in cited] or [datetime.now().isoformat()]
    return {
        "reportDate": datetime.now().isoformat(),
        "reportingInstitution": _REPORTING_INSTITUTION,
        "subject": dict(alert["account"]),
        "typology": triage_result["matchedTypology"],
        "period": {"from": min(times), "to": max(times)},
        "activitySummary": raw["activitySummary"],
        "citedTransactions": cited,
        "groundsForSuspicion": raw["groundsForSuspicion"],
        "recommendedAction": "Escalate to the Financial Intelligence and Enforcement Department (FIED).",
    }
