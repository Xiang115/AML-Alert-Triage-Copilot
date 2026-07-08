"""Knowledge base: load + select the curated typology cards (ADR-0002).

No embeddings, no PDF RAG — the card set is tiny enough to load and pass into
the prompt. Cards live in backend/data/typologies/typologies.json.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from schemas import TypologyCard

_CARDS_FILE = Path(__file__).parent.parent / "data" / "typologies" / "typologies.json"

# Generic AML / ledger words that appear across most cards, so they carry no discriminating
# signal — dropped so ranking keys on the distinctive vocabulary (dormant, structuring, …).
_STOPWORDS = frozenset(
    "the a an of and or to in on is are be by with from into then within after each near no not "
    "little as account funds transaction transactions amount amounts inbound outbound credit debit "
    "it its for that this one single multiple across over under just below above same day days short "
    "window movement value high low new recently opened activity".split()
)


def _tokens(text: str) -> set[str]:
    """Distinctive word tokens: lowercased alphabetic words >3 chars, minus AML stopwords."""
    return {t for t in re.findall(r"[a-z]+", text.lower()) if len(t) > 3 and t not in _STOPWORDS}


@lru_cache(maxsize=1)
def load_cards() -> list[TypologyCard]:
    """All curated typology cards (cached — the file is static)."""
    raw = json.loads(_CARDS_FILE.read_text(encoding="utf-8"))["typologies"]
    return [TypologyCard.model_validate(c) for c in raw]


def get_card(code: str) -> TypologyCard:
    """The card with this code; raises KeyError if there is none."""
    for card in load_cards():
        if card.code == code:
            return card
    raise KeyError(code)


def card_citation(code: str) -> str | None:
    """The section-level regulatory basis for a card (Slice B), or None if the card has none
    or the code is unknown — a missing citation must degrade to 'no policy line', never raise."""
    try:
        return get_card(code).citation
    except KeyError:
        return None


def select_cards(alert=None) -> list[TypologyCard]:
    """Candidate cards for an alert. The set is small, so return all and let the
    triage model pick the match. `alert` is a hook for future narrowing.

    Deliberately returns ALL cards in stable order: that block is the triage prompt's
    DeepSeek-cached prefix, and keeping it whole guarantees recall (the right card is never
    pre-filtered away). Relevance ranking lives in `rank_cards`, which is display-only.
    """
    return load_cards()


@lru_cache(maxsize=1)
def _card_term_index() -> tuple[dict[str, set[str]], dict[str, float]]:
    """Per-card distinctive token sets + an IDF weight per token (rarer across the card
    corpus ⇒ more discriminating). Cached — the card set is static."""
    cards = load_cards()
    terms = {
        c.code: _tokens(" ".join([c.name, c.definition, *c.data_signals, *c.indicators]))
        for c in cards
    }
    df: dict[str, int] = {}
    for ts in terms.values():
        for t in ts:
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log(len(cards) / n) for t, n in df.items()}
    return terms, idf


def rank_cards(evidence: str, cards: list[TypologyCard] | None = None) -> list[tuple[TypologyCard, float]]:
    """Rank candidate cards by IDF-weighted token overlap between the alert evidence and each
    card's vocabulary — a cheap, deterministic relevance pre-rank for the `retrieve` step (NOT
    a decision; triage still reasons over all cards). Recall-preserving: every input card is
    returned, sorted by score descending (stable for ties, so equal scores keep load order)."""
    cards = cards if cards is not None else load_cards()
    terms, idf = _card_term_index()
    ev = _tokens(evidence)
    scored = [
        (c, round(sum(idf.get(t, 0.0) for t in (ev & terms.get(c.code, set()))), 2))
        for c in cards
    ]
    scored.sort(key=lambda cs: cs[1], reverse=True)
    return scored
