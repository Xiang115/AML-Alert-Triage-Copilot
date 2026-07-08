"""Anchoring engine tests — deterministic, no LLM."""

from agents.anchoring import anchor_claims, evidence_integrity
from agents.knowledge_base import get_card
from schemas import ClaimCitation


class _Txn:
    def __init__(self, tid, amount, name):
        self.transaction_id, self.amount, self.counterparty_name = tid, amount, name


def test_self_citation_clamped_to_ledger_and_fired():
    card = get_card("PT-01")
    fired = [card.indicators[0]]
    txns = [_Txn("T-1", 47000.0, "ACME"), _Txn("T-2", 3000.0, "ACME")]
    claims = [
        # cites a real txn + a real fired indicator -> anchored
        ClaimCitation(text="Rapid pass-through of funds", cited_transaction_ids=["T-1"],
                      fired_indicators=[card.indicators[0]]),
        # cites a NON-existent txn and a NON-fired indicator -> nothing survives the clamp -> unanchored
        ClaimCitation(text="No commercial rationale on file", cited_transaction_ids=["T-999"],
                      fired_indicators=["made up indicator"]),
    ]
    traced, unanchored = anchor_claims(
        claims, citable_transactions=txns, fired_indicators=fired,
        matched_typology_name=card.name)

    assert traced[0].anchored is True
    assert traced[0].evidence.transaction_ids == ["T-1"]
    assert traced[0].evidence.fired_indicators == [card.indicators[0]]
    assert traced[1].anchored is False
    assert traced[1].evidence.transaction_ids == []
    assert unanchored == ["No commercial rationale on file"]


def test_keyword_fallback_anchors_without_self_citation():
    # A claim with NO self-citation still anchors if its text names a ledger word + there are txns.
    card = get_card("PT-01")
    txns = [_Txn("T-1", 47000.0, "ACME")]
    claims = [ClaimCitation(text="Balance swept to near zero within hours")]
    traced, _ = anchor_claims(
        claims, citable_transactions=txns, fired_indicators=[], matched_typology_name=card.name)
    assert traced[0].anchored is True
    assert traced[0].evidence.transaction_ids == ["T-1"]


def test_evidence_integrity_counts():
    card = get_card("PT-01")
    txns = [_Txn("T-1", 1.0, "X")]
    claims = [ClaimCitation(text="Balance swept to zero", cited_transaction_ids=["T-1"]),
              ClaimCitation(text="analyst intuition")]
    traced, _ = anchor_claims(claims, citable_transactions=txns, fired_indicators=[],
                              matched_typology_name=None)
    integ = evidence_integrity(traced)
    assert (integ.anchored_count, integ.unanchored_count, integ.total_count) == (1, 1, 2)
