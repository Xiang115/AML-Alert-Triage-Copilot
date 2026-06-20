"""The analyst Decision applied to an Alert (CONTEXT.md: Decision, Disposition).

The disposition->STR invariant lives here as one pure function, off the FastAPI
store: a `dismiss` drops the STR draft; an `escalate` keeps the existing draft, or
replaces it with the analyst's edit. The serving store stays dict (ADR-0008) — the
endpoint applies this result and records a typed `schemas.Decision`.
"""

from __future__ import annotations

from schemas import STRDraft


def resolve_str_draft(
    current: dict | None,
    final_disposition: str,
    edited: STRDraft | None,
) -> dict | None:
    """The STR draft after a decision (as a camelCase dict for the store):
    dropped on `dismiss`; replaced by the analyst's edit on `escalate`, or kept
    as-is when they didn't edit."""
    if final_disposition == "dismiss":
        return None
    if edited is not None:
        return edited.model_dump(by_alias=True, mode="json")
    return current
