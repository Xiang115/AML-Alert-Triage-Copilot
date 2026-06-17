"""Triage agent: pick Escalate/Dismiss against the candidate typology cards.

Serves both data worlds (ADR-0005): demo/hero alerts (transactions) and eval
alerts (aggregated features) — via two evidence renderers. The model returns a
typology *code* and fired indicators; we resolve the card and clamp the
indicators so `source`/membership can't be hallucinated.
"""

from __future__ import annotations

import config
from agents.knowledge_base import get_card
from llm import complete_json

_SYSTEM = (
    "You are an AML alert-triage analyst. Decide Escalate or Dismiss for the alert by "
    "matching it to exactly one of the candidate typology cards. Use each card's indicators "
    "and distinguishing test. Reply ONLY with a JSON object: "
    '{"matchedTypologyCode", "firedIndicators" (subset of that card\'s indicators present in '
    'the evidence), "citedTransactionIds" (ids supporting the call, [] if none), '
    '"recommendation" ("escalate"|"dismiss"), "explanation"}.'
)


def _render_cards(cards: list[dict]) -> str:
    out = []
    for c in cards:
        out.append(
            f"[{c['code']}] {c['name']} (source: {c['source']})\n"
            f"  indicators: {c['indicators']}\n"
            f"  distinguishing test: {c['distinguishingTest']}"
        )
    return "\n".join(out)


def render_alert_evidence(alert: dict) -> str:
    """Evidence block for a demo/hero alert (clean transactions)."""
    acct = alert["account"]
    lines = [
        f"Account: {acct['holderName']} ({acct['accountType']}, opened {acct['openedAt']})",
        f"Trigger: {alert['trigger']}",
        "Transactions (id | time | dir | amount | counterparty | runningBalance):",
    ]
    for t in alert.get("transactions") or []:
        lines.append(
            f"  {t['transactionId']} | {t['timestamp']} | {t['direction']} | "
            f"{t['amount']} {t['currency']} | {t['counterpartyName']} | {t['runningBalance']}"
        )
    return "\n".join(lines)


def render_features_evidence(features: dict) -> str:
    """Evidence block for an eval alert (aggregated features, no transactions)."""
    return "Aggregated alert features:\n" + "\n".join(f"  {k}: {v}" for k, v in features.items())


def triage(evidence: str, cards: list[dict], *, client=None, model: str | None = None) -> dict:
    raw = complete_json(
        _SYSTEM,
        f"Candidate typologies:\n{_render_cards(cards)}\n\nAlert evidence:\n{evidence}",
        model or config.MODEL_WORKHORSE,
        client=client,
    )
    card = get_card(raw["matchedTypologyCode"])
    fired = [i for i in raw.get("firedIndicators", []) if i in card["indicators"]]
    return {
        "recommendation": raw["recommendation"],
        "matchedTypology": {"code": card["code"], "name": card["name"], "source": card["source"]},
        "firedIndicators": fired,
        "citedTransactionIds": raw.get("citedTransactionIds", []),
        "explanation": raw.get("explanation", ""),
    }
