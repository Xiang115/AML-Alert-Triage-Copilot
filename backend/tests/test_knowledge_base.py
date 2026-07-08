import pytest

from agents.knowledge_base import card_citation, get_card, load_cards, rank_cards


def test_rank_cards_surfaces_the_matching_typology_first():
    # trigger vocabulary maps to the card; the pre-rank must put the right candidate on top
    assert rank_cards("Rapid in-out movement on a recently opened low-activity account")[0][0].code == "PT-01"
    assert rank_cards("Account dormant 16 months then reactivated by a large inbound credit")[0][0].code == "DA-01"
    assert rank_cards("Repeated cash deposits just below the CTR threshold across branches")[0][0].code == "ST-01"
    assert rank_cards("Numerous inbound transfers from unrelated individuals consolidated then forwarded")[0][0].code == "FI-01"


def test_rank_cards_is_recall_preserving_and_sorted_descending():
    ranked = rank_cards("any evidence text whatsoever")
    # the ranking never drops a candidate — every card survives (recall guarantee)
    assert {c.code for c, _ in ranked} == {c.code for c in load_cards()}
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_load_cards_returns_the_curated_set():
    cards = load_cards()
    assert len(cards) >= 5
    for field in ("code", "name", "source", "indicators", "distinguishing_test", "benign_lookalike"):
        assert hasattr(cards[0], field)


def test_get_card_by_code():
    assert "Structuring" in get_card("ST-01").name


def test_get_card_unknown_raises():
    with pytest.raises(KeyError):
        get_card("ZZ-99")


def test_every_card_carries_a_citation():
    # Slice B: each curated card has a verified regulatory citation for the STR policy line
    for card in load_cards():
        assert card.citation, f"{card.code} is missing a citation"
        assert "FATF Recommendation" in card.citation


def test_card_citation_accessor_degrades_on_unknown_code():
    assert card_citation("PT-01") == get_card("PT-01").citation
    assert card_citation("ZZ-99") is None  # unknown code => None, never raises
