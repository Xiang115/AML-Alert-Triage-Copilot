"""Decision-layer tests: STR resolution plus Slice A learning-loop persistence."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone

import pytest

import decision
import store
from decision import final_disposition_for, resolve_str_draft
from schemas import Decision, STRDraft


def _str_draft() -> STRDraft:
    # DQ-003 (an escalate) carries a precomputed STRDraft; reuse its shape.
    for a in json.load(open("data/results.json")):
        draft = a["triage"]["strDraft"]
        if draft is not None:
            return STRDraft.model_validate(draft)
    raise AssertionError("no escalate with an strDraft in results.json")


@pytest.mark.parametrize(
    ("recommendation", "action", "expected"),
    [
        ("escalate", "approve", "escalate"),
        ("dismiss", "approve", "dismiss"),
        ("escalate", "override", "dismiss"),
        ("dismiss", "override", "escalate"),
    ],
)
def test_final_disposition_is_derived_from_ai_call_and_human_action(recommendation, action, expected):
    assert final_disposition_for(recommendation, action) == expected


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


@pytest.fixture
def memory_store():
    """Point the global store at an isolated in-memory SQLite db for one test."""
    saved = (store._engine, store._seed, store._alert_seed)
    store._seed = []
    store._alert_seed = []
    store.init("sqlite://")
    store.reset()
    yield
    store._engine, store._seed, store._alert_seed = saved


def _memory_module():
    return importlib.import_module("agents.memory")


def _learn_from_decision():
    fn = getattr(decision, "learn_from_decision", None)
    assert callable(fn), "decision.learn_from_decision is not implemented"
    return fn


def _txn(
    txn_id: str,
    *,
    counterparty_name: str | None = None,
    counterparty_account: str | None = None,
) -> dict:
    return {
        "transactionId": txn_id,
        "counterpartyName": counterparty_name,
        "counterpartyAccount": counterparty_account,
    }


def _alert(
    *transactions: dict,
    alert_id: str,
    code: str = "FI-01",
    cited_ids: list[str] | None = None,
) -> dict:
    return {
        "alertId": alert_id,
        "transactions": list(transactions),
        "triage": {
            "matchedTypology": {"code": code},
            "citedTransactionIds": cited_ids or [],
        },
    }


def _decision(alert_id: str, final_disposition: str, decided_at: datetime) -> Decision:
    return Decision(
        alert_id=alert_id,
        action="approve",
        final_disposition=final_disposition,
        edited_str_draft=None,
        note=None,
        decided_at=decided_at,
    )


def test_learn_from_decision_records_a_clearance_on_dismiss(memory_store):
    alert = _alert(
        _txn("T-1", counterparty_account="acme-123"),
        _txn("T-2", counterparty_account="acme-123"),
        alert_id="SD-00021",
    )
    decided_at = datetime(2026, 7, 2, 9, 14, tzinfo=timezone(timedelta(hours=8)))

    _learn_from_decision()(alert, _decision("SD-00021", "dismiss", decided_at))

    pattern = store.find_cleared_pattern(_memory_module().signature(alert))
    assert pattern is not None
    assert pattern["sourceDecisionId"] == "SD-00021"
    assert pattern["sourceAlertId"] == "SD-00021"
    assert pattern["clearedCount"] == 1
    assert pattern["clearedAt"] == decided_at.isoformat()


def test_learn_from_decision_is_a_noop_on_escalate(memory_store):
    alert = _alert(
        _txn("T-1", counterparty_account="acme-123"),
        _txn("T-2", counterparty_account="acme-123"),
        alert_id="SD-00021",
    )

    _learn_from_decision()(alert, _decision("SD-00021", "escalate", datetime.now(timezone.utc)))

    assert store.find_cleared_pattern(_memory_module().signature(alert)) is None


def test_learn_from_decision_increments_cleared_count_for_a_repeat_dismiss(memory_store):
    first = _alert(
        _txn("T-1", counterparty_account="acme-123"),
        _txn("T-2", counterparty_account="acme-123"),
        alert_id="SD-00021",
    )
    second = _alert(
        _txn("T-3", counterparty_account="acme-123"),
        _txn("T-4", counterparty_account="acme-123"),
        alert_id="SD-00022",
    )
    learn = _learn_from_decision()

    learn(first, _decision("SD-00021", "dismiss", datetime(2026, 7, 2, 9, 14, tzinfo=timezone.utc)))
    learn(second, _decision("SD-00022", "dismiss", datetime(2026, 7, 2, 10, 14, tzinfo=timezone.utc)))

    pattern = store.find_cleared_pattern(_memory_module().signature(first))
    assert pattern is not None
    assert pattern["clearedCount"] == 2
