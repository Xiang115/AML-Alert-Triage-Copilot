"""Unit tests for the disposition->STR rule — pure, no HTTP, no store."""

import json

from decision import resolve_str_draft
from schemas import STRDraft


def _str_draft() -> STRDraft:
    # DQ-003 (an escalate) carries a precomputed STRDraft; reuse its shape.
    for a in json.load(open("data/results.json")):
        draft = a["triage"]["strDraft"]
        if draft is not None:
            return STRDraft.model_validate(draft)
    raise AssertionError("no escalate with an strDraft in results.json")


def test_dismiss_drops_the_str_draft():
    current = _str_draft().model_dump(by_alias=True, mode="json")
    assert resolve_str_draft(current, "dismiss", None) is None


def test_escalate_without_edit_keeps_current_draft():
    current = _str_draft().model_dump(by_alias=True, mode="json")
    assert resolve_str_draft(current, "escalate", None) == current


def test_escalate_with_edit_replaces_draft():
    current = _str_draft().model_dump(by_alias=True, mode="json")
    edited = _str_draft()
    edited.activity_summary = "Analyst-edited summary."
    out = resolve_str_draft(current, "escalate", edited)
    assert out["activitySummary"] == "Analyst-edited summary."
    assert out != current
