import pytest

from agents.knowledge_base import get_card, load_cards


def test_load_cards_returns_the_curated_set():
    cards = load_cards()
    assert len(cards) >= 5
    for field in ("code", "name", "source", "indicators", "distinguishingTest", "benignLookalike"):
        assert field in cards[0]


def test_get_card_by_code():
    assert "Structuring" in get_card("ST-01")["name"]


def test_get_card_unknown_raises():
    with pytest.raises(KeyError):
        get_card("ZZ-99")
