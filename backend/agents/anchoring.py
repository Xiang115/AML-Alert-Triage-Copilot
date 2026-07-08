"""Shared claim-anchoring engine (ADR-0022, generalising ADR-0013).

One engine, three call sites: STR grounds (str_drafter), triage claims, verifier claims. Each claim
may arrive with the model's self-citation (transaction ids + fired indicators); we take the UNION of
that (clamped to the real ledger + fired set) and the keyword/ledger-word derivation, then split
Anchored from Unanchored. Provenance, not proof. Pure/deterministic — no LLM, safe on the demo path.
"""

from __future__ import annotations

import re

from schemas import ClaimCitation, ClaimEvidence, EvidenceIntegrity, TracedClaim

# Ledger vocabulary — words that mean a claim is *describing the cited transactions* (ADR-0013), so it
# anchors even when it names no id/amount/counterparty. Excludes generic inference words so evaluative
# claims ("inconsistent with the account profile") stay Unanchored. Substring stems keep it cheap.
_LEDGER_WORDS = (
    "balance", "swept", "sweep", "drain", "zero", "deplet", "empt",
    "dormant", "inactive", "sudden", "burst", "rapid", "immediat", "within",
    "hours", "minutes", "overnight", "same day", "same-day", "timeframe",
    "inbound", "outbound", "inflow", "outflow", "incoming", "outgoing",
    "credit", "debit", "deposit", "transfer", "payment", "remit", "onward",
    "aggregat", "consolidat", "layering", "structur", "concentrat", "uniform",
    "counterpart", "sender", "remitter", "recipient", "beneficiar", "third part", "individuals",
    "gbp", "eur", "usd", "myr", "sgd", "cross-border", "currenc", "foreign",
)


def _kw_overlap(indicator: str, claim_lower: str) -> bool:
    """True when a fired indicator and a claim share >=2 distinctive (>4-char) words."""
    words = {w for w in re.findall(r"[a-z]+", indicator.lower()) if len(w) > 4}
    return sum(1 for w in words if w in claim_lower) >= 2


def anchor_claims(
    claims: list[ClaimCitation],
    *,
    citable_transactions: list,
    fired_indicators: list[str],
    matched_typology_name: str | None,
    policy_line: str | None = None,
    citation: str | None = None,
) -> tuple[list[TracedClaim], list[str]]:
    """Trace each claim to its evidence and split Anchored from Unanchored.

    `citable_transactions` are the transactions whose ids/amounts/counterparties may anchor a claim
    (STR: the cited/filed legs; triage: all alert transactions). A claim anchors when — after clamping
    — it names/cites a citable transaction, restates a fired indicator, restates the typology, or IS
    the explicit policy-basis line. Returns (traced_claims, unanchored_texts)."""
    citable_ids = [t.transaction_id for t in citable_transactions]
    id_set = set(citable_ids)
    amounts = {f"{t.amount:g}" for t in citable_transactions}
    parties = {t.counterparty_name.lower() for t in citable_transactions if t.counterparty_name}
    typ_words = {w for w in re.findall(r"[a-z]+", (matched_typology_name or "").lower()) if len(w) > 5}

    traced: list[TracedClaim] = []
    unanchored: list[str] = []
    for c in claims:
        g = c.text
        gl = g.lower()
        if policy_line and g == policy_line:  # the explicit, verified policy-basis line (STR)
            traced.append(TracedClaim(text=g, anchored=True, evidence=ClaimEvidence(citation=citation)))
            continue
        # transactions: ids named in the text, plus the model's self-citation (clamped), plus the
        # "describes the cited set" fallback when the text carries ledger vocabulary.
        tx = [tid for tid in citable_ids if tid.lower() in gl]
        for tid in c.cited_transaction_ids:
            if tid in id_set and tid not in tx:
                tx.append(tid)
        if not tx and citable_ids and (
            any(a in g for a in amounts) or any(p in gl for p in parties)
            or any(w in gl for w in _LEDGER_WORDS)
        ):
            tx = list(citable_ids)
        # indicators: the model's self-cited fired indicators (clamped to what actually fired), plus
        # keyword-overlap with any fired indicator.
        inds = [i for i in c.fired_indicators if i in fired_indicators]
        for i in fired_indicators:
            if i not in inds and _kw_overlap(i, gl):
                inds.append(i)
        typ = matched_typology_name if typ_words and any(w in gl for w in typ_words) else None
        anchored = bool(tx or inds or typ)
        traced.append(TracedClaim(
            text=g, anchored=anchored,
            evidence=ClaimEvidence(transaction_ids=tx, fired_indicators=inds, matched_typology=typ)))
        if not anchored:
            unanchored.append(g)
    return traced, unanchored


def evidence_integrity(traced: list[TracedClaim]) -> EvidenceIntegrity:
    anchored = sum(1 for c in traced if c.anchored)
    return EvidenceIntegrity(
        anchored_count=anchored, unanchored_count=len(traced) - anchored, total_count=len(traced))
