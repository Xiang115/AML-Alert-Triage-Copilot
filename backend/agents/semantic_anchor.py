"""LLM semantic anchor (ADR-0013 deepening) — a cheap MODEL_VERIFIER pass that judges whether the
cited evidence actually *substantiates* each drafted grounds-claim, catching what the deterministic
keyword anchor cannot: a claim that only coincidentally shares words with a transaction (a false
keep), or a genuine support the keywords never saw (a false drop).

OFF the deterministic demo path (ADR-0003). The frozen results.json is built WITHOUT it (precompute
passes `semantic=False`), so the filmed demo stays deterministic and token-free. It runs only when
explicitly enabled — the live `/triage?semantic=true` Q&A, or a one-off offline script — so it never
bakes model non-determinism into the served artifact, and never costs a token unless asked for.

One batched MODEL_VERIFIER (flash) call per escalated STR: all claims judged together, so the whole
review is a single cheap request. Provenance-vs-correctness still holds — this is a second opinion on
support, surfaced to the analyst, never an automatic edit to the filed report.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator

import config
from llm import coerce_text, complete_model
from schemas import LLMResponse, STRDraft, TriageOutput, TypologyCard

_SYSTEM = (
    "You are an AML compliance reviewer checking a draft Suspicious Transaction Report. For each "
    "numbered claim, decide whether the LISTED EVIDENCE substantiates it. Judge ONLY against the "
    "evidence given, not general plausibility. 'supported' = the evidence clearly backs the claim; "
    "'unsupported' = the evidence does not back it, or contradicts it; 'unclear' = the evidence is "
    "insufficient to decide. Reply ONLY with JSON: "
    '{"verdicts": [{"index": <the integer from the list>, '
    '"verdict": "supported" | "unsupported" | "unclear", "reason": "<one short sentence>"}]}.'
)


class _ClaimVerdict(LLMResponse):
    index: int
    verdict: Literal["supported", "unsupported", "unclear"]
    reason: str

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalize_verdict(cls, v):
        # Robust to model phrasing ("Supported", "not supported", "contradicted") so a valid
        # judgment never fails validation and burns a retry. Check unsupported FIRST — the word
        # "unsupported" contains "support".
        s = str(v).strip().lower()
        if "unsupport" in s or "not support" in s or "contradict" in s:
            return "unsupported"
        if "support" in s:
            return "supported"
        return "unclear"

    @field_validator("reason", mode="before")
    @classmethod
    def _coerce_reason(cls, v):
        return coerce_text(v)


class _Verdicts(LLMResponse):
    verdicts: list[_ClaimVerdict]


def _evidence_block(str_draft: STRDraft, triage: TriageOutput, card: TypologyCard) -> str:
    parts = [f"Matched typology: {str_draft.typology.name}"]
    if triage.fired_indicators:
        parts.append("Fired indicators:\n" + "\n".join(f"  - {ind}" for ind in triage.fired_indicators))
    if str_draft.cited_transactions:
        parts.append(
            "Cited transactions (id | amount | counterparty | runningBalance):\n"
            + "\n".join(
                f"  {t.transaction_id} | {t.amount:g} {t.currency} | {t.counterparty_name} | "
                f"runningBalance {t.running_balance:g}"
                for t in str_draft.cited_transactions
            )
        )
    if card.citation:
        parts.append(f"Policy basis: {card.citation}")
    return "\n".join(parts)


def semantic_review(
    str_draft: STRDraft, triage: TriageOutput, card: TypologyCard, *, client=None, model: str | None = None
) -> STRDraft:
    """Return a copy of `str_draft` whose `traced_claims` carry an LLM `semantic_verdict` + reason.

    One batched MODEL_VERIFIER call. A no-op (no call, returned unchanged) when there are no claims.
    Claims the model does not return a verdict for keep `semantic_verdict=None`."""
    claims = list(str_draft.traced_claims or [])
    if not claims:
        return str_draft

    user = (
        f"Evidence:\n{_evidence_block(str_draft, triage, card)}\n\n"
        "Claims:\n" + "\n".join(f"{i}. {c.text}" for i, c in enumerate(claims))
    )
    out = complete_model(
        _SYSTEM, user, model or config.MODEL_VERIFIER, _Verdicts, client=client, max_tokens=4096
    )
    by_index = {v.index: v for v in out.verdicts}
    reviewed = [
        c.model_copy(update={"semantic_verdict": by_index[i].verdict, "semantic_reason": by_index[i].reason})
        if i in by_index
        else c
        for i, c in enumerate(claims)
    ]
    return str_draft.model_copy(update={"traced_claims": reviewed})
