"""Analyst handbook via live DeepSeek RAG.

Retrieve the most relevant knowledge-base passages (agents/kb_retrieval — BM25, optionally
hybridised with semantic embeddings), then DeepSeek writes the 'what to check' checklist using
ONLY those passages and cites the source page. This is real retrieve-augment-generate: the checks
are grounded in the actual BNM/FATF/APG/FinCEN text, not synthesised from the model's memory.
"""

from __future__ import annotations

import config
from agents.kb_retrieval import retrieve
from llm import complete_model
from schemas import CoachingHandbook, HandbookCheck, LLMResponse, TypologyCard

_SYSTEM = (
    "You are an AML training lead writing a concise 'what to check' checklist for a junior analyst "
    "reviewing an alert of the given money-laundering typology. Use ONLY the numbered SOURCE "
    "EXCERPTS provided — do NOT introduce red flags they do not support. Write 3 to 5 specific, "
    "actionable checks in plain imperative English. Each check MUST cite the single excerpt number "
    "it rests on. Reply ONLY with JSON: "
    '{"whatToCheck": [{"check": "<imperative check>", "source": <excerpt number>}]}'
)


class _Check(LLMResponse):
    check: str
    source: int  # 1-based excerpt number the check is grounded in


class _HandbookResponse(LLMResponse):
    what_to_check: list[_Check]


def _query(card: TypologyCard) -> str:
    """The retrieval query for a typology: its distinctive vocabulary (name + definition +
    indicators + distinguishing test) so BM25/semantic pull the passages that describe it."""
    return " ".join([card.name, card.definition, *card.indicators, card.distinguishing_test])


def generate_handbook(card: TypologyCard, *, client=None, k: int = 6,
                      model: str | None = None) -> CoachingHandbook:
    """Live RAG: retrieve k KB passages for this typology, then DeepSeek writes the checklist
    grounded only in them, each check cited to its source document + page."""
    chunks = retrieve(_query(card), k=k)
    excerpts = "\n\n".join(
        f"[{i + 1}] ({c['source']}, p.{c['page']}) {c['text']}" for i, c in enumerate(chunks)
    )
    parsed = complete_model(
        _SYSTEM,
        f"Typology: {card.name}\nDefinition: {card.definition}\n\nSOURCE EXCERPTS:\n{excerpts}",
        model or config.MODEL_WORKHORSE,
        _HandbookResponse,
        client=client,
    )

    checks: list[HandbookCheck] = []
    for item in parsed.what_to_check:
        idx = item.source - 1
        src = (f"{chunks[idx]['source']}, p.{chunks[idx]['page']}"
               if 0 <= idx < len(chunks) else "knowledge base")
        checks.append(HandbookCheck(check=item.check, source=src))

    sources = sorted({c["source"] for c in chunks})
    return CoachingHandbook(typology_code=card.code, what_to_check=checks, sources=sources)
