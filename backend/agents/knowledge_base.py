"""Knowledge base: load + select the curated typology cards (ADR-0002).

No embeddings, no PDF RAG — the card set is tiny enough to load and pass into
the prompt. Cards live in backend/data/typologies/typologies.json.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CARDS_FILE = Path(__file__).parent.parent / "data" / "typologies" / "typologies.json"


@lru_cache(maxsize=1)
def load_cards() -> list[dict]:
    """All curated typology cards (cached — the file is static)."""
    return json.loads(_CARDS_FILE.read_text(encoding="utf-8"))["typologies"]


def get_card(code: str) -> dict:
    """The card with this code; raises KeyError if there is none."""
    for card in load_cards():
        if card["code"] == code:
            return card
    raise KeyError(code)


def select_cards(alert=None) -> list[dict]:
    """Candidate cards for an alert. The set is small, so return all and let the
    triage model pick the match. `alert` is a hook for future narrowing.
    """
    return load_cards()
