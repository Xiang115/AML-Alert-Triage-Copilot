"""STR drafter (ADR-0006): a structured STRDraft object, only on escalate.

The model writes the two editable narrative fields (activitySummary,
groundsForSuspicion); everything else is assembled deterministically from the
alert + matched typology, so the structured report can't be hallucinated.
"""

from __future__ import annotations

import re
from datetime import datetime

import config
from agents.anchoring import anchor_claims
from llm import complete_model
from schemas import (
    AlertInput,
    CitedTransaction,
    ClaimCitation,
    ClaimEvidence,
    LLMResponse,
    Period,
    STRDraft,
    TracedClaim,
    TriageOutput,
    TypologyCard,
)

_REPORTING_INSTITUTION = "Demo Bank Berhad"
_FIED = "the Financial Intelligence and Enforcement Department (FIED)"


def policy_basis_line(citation: str | None) -> str | None:
    """The single 'Policy basis: …' sentence surfaced on the STR (Slice B), or None when the
    card carries no citation. Shared by the STR grounds and the recommended action so the text
    is byte-identical everywhere and idempotent to re-apply (the precompute backfill relies on
    matching it exactly to avoid duplicating the line)."""
    return f"Policy basis: {citation}." if citation else None


def recommended_action(verifier_status: str, typology_name: str, citation: str | None = None) -> str:
    """The STR's recommended next step (ADR-0006), derived from the call's signals rather
    than a fixed string: a verifier flag means a human must confirm the pattern before the
    bank files; otherwise it names the matched typology so the action reads case-specific.
    When the matched card carries a `citation`, the policy basis is appended (Slice B)."""
    if verifier_status == "flagged":
        base = (
            f"Hold for analyst confirmation before filing — the verifier flagged this "
            f"{typology_name} call; escalate to {_FIED} only once the pattern is substantiated."
        )
    else:
        base = f"File an STR with {_FIED} for the identified {typology_name} pattern."
    line = policy_basis_line(citation)
    return f"{base} {line}" if line else base

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


# Narrative figure check (ADR-0013 deepening). A currency amount in the narrative must equal a real
# ledger value or it is flagged. `_AMOUNT_RE` finds currency amounts; a bare integer (a count, a
# date, a year) is deliberately NOT an amount — only a currency symbol/code, a thousands separator, a
# decimal, or a k/m magnitude qualifies it.
_APPROX_WORDS = (
    "over", "about", "approx", "around", "nearly", "roughly", "~",
    "more than", "in excess of", "up to", "at least", "almost",
)
_CURRENCY = r"(?:RM|MYR|GBP|EUR|USD|SGD|£|€|\$)"
# A k/m magnitude only counts when it is a standalone suffix — `(?![A-Za-z])` stops the 'M' of
# 'Mexican' / 'Movement' being read as millions and corrupting a real figure.
_AMOUNT_RE = re.compile(
    rf"({_CURRENCY}\s?)?(\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+\.\d+|\d+)(?:\s?([kKmM])(?![A-Za-z]))?"
)


def _extract_amounts(text: str) -> list[dict]:
    """Pull currency amounts out of a narrative. Returns {text, value, approx, k} per amount. A token
    qualifies as an amount only with a currency symbol/code, a thousands separator, or a k/m suffix —
    so bare integers and lone decimals (a count, a date, a '2.5-hour period') are NOT amounts."""
    out: list[dict] = []
    for m in _AMOUNT_RE.finditer(text):
        cur, num, mag = m.group(1), m.group(2), m.group(3)
        if not (cur or "," in num or mag):
            continue  # no currency / separator / magnitude -> a count, date, or duration, not money
        value = float(num.replace(",", ""))
        if mag and mag.lower() == "k":
            value *= 1_000
        elif mag and mag.lower() == "m":
            value *= 1_000_000
        preceding = text[max(0, m.start() - 25):m.start()].lower()
        out.append({
            "text": m.group(0).strip(),
            "value": value,
            "approx": any(w in preceding for w in _APPROX_WORDS),
            "k": bool(mag),
        })
    return out


def _check_narrative_figures(alert, triage, summary: str):
    """Check every currency amount in the drafted narrative against the ledger (ADR-0013). Each
    amount is pinned to the cited transaction / total / running-balance it equals — or, if it equals
    none of them, flagged `unverified` (the fabricated-figure catch). Sum- and balance-aware (incl.
    the balance just before each transaction) so a legitimate total or opening balance is not
    false-flagged; k-suffixed and approximate figures ('over £114k') match within tolerance."""
    from collections import defaultdict

    from schemas import NarrativeFigure

    txns = list(alert.transactions or [])
    if not txns or not summary:
        return []
    cited_ids = set(triage.cited_transaction_ids)
    cited = [t for t in txns if t.transaction_id in cited_ids] or txns

    # A figure is real if it equals any alert transaction's amount or running balance (incl. the
    # balance just before it), or any natural subtotal — the full/inbound/outbound sum of the cited
    # set or of the whole alert. Narratives routinely quote a subtotal ("six inbound totalling X")
    # or a residual balance, so all of these must count or legitimate figures get false-flagged.
    amt_map: dict[float, list[str]] = defaultdict(list)
    bal_map: dict[float, list[str]] = defaultdict(list)
    for t in txns:
        amt_map[round(t.amount, 2)].append(t.transaction_id)
        bal_map[round(t.running_balance, 2)].append(t.transaction_id)
        pre = t.running_balance - t.amount if t.direction == "inbound" else t.running_balance + t.amount
        bal_map[round(pre, 2)].append(t.transaction_id)

    def _sum(ts, direction=None):
        return round(sum(t.amount for t in ts if direction is None or t.direction == direction), 2)

    totals = {_sum(g, d) for g in (cited, txns) for d in (None, "inbound", "outbound")}
    all_ids = [t.transaction_id for t in cited]

    def near(mapping: dict[float, list[str]], a: float, tol: float):
        for k, ids in mapping.items():
            if abs(k - a) <= tol:
                return ids
        return None

    figures, seen = [], set()
    for f in _extract_amounts(summary):
        if f["text"] in seen:
            continue
        seen.add(f["text"])
        a, tol = f["value"], (1000.0 if f["k"] else (max(1.0, 0.01 * f["value"]) if f["approx"] else 0.5))
        hit = near(amt_map, a, tol)
        if hit:
            figures.append(NarrativeFigure(text=f["text"], kind="transaction", transaction_ids=hit))
        elif near(bal_map, a, tol):
            figures.append(NarrativeFigure(text=f["text"], kind="balance",
                                           transaction_ids=near(bal_map, a, tol)))
        elif any(abs(a - s) <= max(tol, 0.5) for s in totals):
            figures.append(NarrativeFigure(text=f["text"], kind="total", transaction_ids=all_ids))
        else:
            figures.append(NarrativeFigure(text=f["text"], kind="unmatched"))
    return figures


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


def draft_str(alert: AlertInput, triage_result: TriageOutput, card: TypologyCard, *,
              verifier_status: str = "agreed", client=None, model: str | None = None) -> STRDraft | None:
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
        f"Triage grounds: {[c.text for c in triage_result.claims]}\n"
        f"Account holder: {alert.account.holder_name}\n"
        f"Cited transactions (id | time | amount | counterparty | runningBalance):\n{txn_lines}\n"
        f"Narrative hints: {card.str_narrative_hints}",
        model or config.MODEL_WORKHORSE,
        _StrNarrative,
        client=client,
        max_tokens=8192,  # STR narrative + reasoning tokens; sized well above the burst
        stage="strDrafter",
        template_id="str-drafter-v1",
    )

    # Append the card's policy basis to the grounds (Slice B) — a deterministic, verified line,
    # not a model claim. Guarded so a re-draft never duplicates it.
    grounds = list(narrative.grounds_for_suspicion)
    policy_line = policy_basis_line(card.citation)
    if policy_line and policy_line not in grounds:
        grounds.append(policy_line)

    # Evidence-Anchored STR (ADR-0013 via the shared ADR-0022 engine): trace each ground to concrete
    # evidence and pull the untraceable ones from the FILED draft. Deterministic, no LLM.
    cited_ids = set(triage_result.cited_transaction_ids)
    cited_txns = [t for t in (alert.transactions or []) if t.transaction_id in cited_ids]
    traced, unanchored = anchor_claims(
        [ClaimCitation(text=g) for g in grounds],
        citable_transactions=cited_txns,
        fired_indicators=triage_result.fired_indicators,
        matched_typology_name=triage_result.matched_typology.name if triage_result.matched_typology else None,
        policy_line=policy_line,
        citation=card.citation,
    )
    filed = [c.text for c in traced if c.anchored]
    if not filed:
        # All-unanchored guard: never ship an empty grounds list. Keep the originals but record that
        # nothing anchored — a data-quality signal, not a silent empty report.
        filed = grounds
        traced = [TracedClaim(text=g, evidence=ClaimEvidence(), anchored=False) for g in grounds]
        unanchored = []

    # Check every currency amount in the narrative against the ledger (ADR-0013 deepening). Prose is
    # never pruned — activity_summary is kept intact — and each figure is pinned to the transaction /
    # total / balance it equals, or flagged 'unverified' (the fabricated-figure catch).
    narrative_figures = _check_narrative_figures(alert, triage_result, narrative.activity_summary)

    times = [t.timestamp for t in cited] or [datetime.now()]
    return STRDraft(
        report_date=datetime.now(),
        reporting_institution=_REPORTING_INSTITUTION,
        subject=alert.account,
        typology=triage_result.matched_typology,
        period=Period(**{"from": min(times), "to": max(times)}),
        activity_summary=narrative.activity_summary,
        cited_transactions=cited,
        grounds_for_suspicion=filed,
        traced_claims=traced,
        unanchored_claims=unanchored,
        narrative_figures=narrative_figures,
        recommended_action=recommended_action(
            verifier_status, triage_result.matched_typology.name, card.citation),
    )
