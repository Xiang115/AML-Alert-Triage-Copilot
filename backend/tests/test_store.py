"""The store: persistence is the whole point, so prove it survives a 'restart'.

Each test points the store at a throwaway SQLite FILE db (not the suite's shared
in-memory db), then restores the global engine so the API tests that follow are
unaffected. File-restart survival is the guarantee in-memory dicts could never give.
"""

import pytest

import store


@pytest.fixture
def temp_store(tmp_path):
    """Point the store at a throwaway file db for one test, then restore the global
    engine + seed the rest of the suite relies on."""
    saved = (store._engine, store._seed, store._alert_seed)
    url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    store._seed = []        # start unseeded; tests opt into a seed explicitly
    store._alert_seed = []  # ditto for the alert catalog
    store.init(url)
    yield url
    store._engine, store._seed, store._alert_seed = saved  # restore the suite's shared store


def test_decision_is_recorded_and_read_back(temp_store):
    store.record_decision("DQ-001", {"alertId": "DQ-001", "action": "approve"})
    assert store.get_decision("DQ-001") == {"alertId": "DQ-001", "action": "approve"}
    assert store.get_decision("NOPE") is None


def test_latest_decision_wins(temp_store):
    store.record_decision("DQ-001", {"action": "approve"})
    store.record_decision("DQ-001", {"action": "override"})  # change of mind
    assert store.get_decision("DQ-001") == {"action": "override"}  # upsert, not duplicate
    assert len(store.all_decisions()) == 1


def test_audit_is_append_only_and_ordered(temp_store):
    store.append_audit({"event": "decision", "n": 1})
    store.append_audit({"event": "submission", "n": 2})
    assert [e["n"] for e in store.all_audit()] == [1, 2]  # insertion order preserved


def test_decision_and_audit_survive_a_restart(temp_store):
    """The real guarantee: re-open the same db file (a process restart) and the data is
    still there — what the in-memory dicts could never do."""
    store.record_decision("HERO-002", {"action": "approve", "finalDisposition": "escalate"})
    store.append_audit({"event": "submission", "submissionRef": "MYFIU-2026-000123"})

    store.init(temp_store)  # reconnect to the same file = a restart

    assert store.get_decision("HERO-002") == {"action": "approve", "finalDisposition": "escalate"}
    assert store.all_audit() == [{"event": "submission", "submissionRef": "MYFIU-2026-000123"}]


def test_reset_clears_decisions_and_reseeds_audit(temp_store):
    store.seed_audit([{"event": "autoClear", "alertId": "DQ-009"}])
    store.record_decision("DQ-001", {"action": "approve"})
    store.append_audit({"event": "decision", "alertId": "DQ-001"})

    store.reset()

    assert store.all_decisions() == []  # session decisions dropped
    assert store.all_audit() == [{"event": "autoClear", "alertId": "DQ-009"}]  # seed restored only


def test_seed_only_takes_when_trail_is_empty(temp_store):
    seed = [{"event": "autoClear", "alertId": "DQ-009"}]
    store.seed_audit(seed)
    store.seed_audit(seed)  # a second seed (e.g. a restart) must not duplicate
    assert len(store.all_audit()) == 1


def test_migrate_timestamps_relabels_naive_stamps_to_gmt8(temp_store):
    # A legacy audit row + decision written before the GMT+8 fix: naive (UTC, "UK time").
    store.append_audit({"event": "autoClear", "alertId": "DQ-1", "at": "2026-06-25T22:50:39"})
    store.record_decision("DQ-1", {"action": "approve", "decidedAt": "2026-06-25T22:50:39"})

    changed = store.migrate_timestamps_to_local()

    assert changed == 2  # both rows rewritten
    assert store.all_audit()[0]["at"] == "2026-06-25T22:50:39+08:00"
    assert store.get_decision("DQ-1")["decidedAt"] == "2026-06-25T22:50:39+08:00"


def test_migrate_timestamps_is_idempotent(temp_store):
    store.append_audit({"event": "autoClear", "alertId": "DQ-1", "at": "2026-06-25T22:50:39+08:00"})
    assert store.migrate_timestamps_to_local() == 0  # already local -> no rewrite


# --- alert catalog (input data) ----------------------------------------------------

def _alert(aid: str, *, status: str = "pending", routing: str = "needsReview", txns: int = 2) -> dict:
    return {
        "alertId": aid,
        "status": status,
        "routing": routing,
        "triage": {"recommendation": "dismiss", "strDraft": None},
        "transactions": [{"transactionId": f"{aid}-T{i}", "amount": i} for i in range(txns)],
    }


def test_seed_alerts_splits_into_alert_and_transaction_rows(temp_store):
    store.seed_alerts([_alert("DQ-100", txns=2), _alert("DQ-101", txns=3)])
    assert store.count_alerts() == 2
    assert store.count_transactions() == 5  # one row per ledger entry — the table that scales


def test_list_alerts_filters_on_indexed_columns(temp_store):
    store.seed_alerts([
        _alert("A", status="pending", routing="needsReview"),
        _alert("B", status="approved", routing="autoCleared"),
    ])
    assert {a["alertId"] for a in store.list_alerts()} == {"A", "B"}
    assert [a["alertId"] for a in store.list_alerts(status="approved")] == ["B"]
    assert [a["alertId"] for a in store.list_alerts(routing="autoCleared")] == ["B"]
    assert all(a["transactions"] is None for a in store.list_alerts())  # queue omits txns


def test_get_alert_includes_transactions_in_ledger_order(temp_store):
    store.seed_alerts([_alert("DQ-100", txns=3)])
    a = store.get_alert("DQ-100")
    assert [t["transactionId"] for t in a["transactions"]] == ["DQ-100-T0", "DQ-100-T1", "DQ-100-T2"]
    assert store.get_alert("NOPE") is None


def test_set_alert_decision_persists_and_survives_restart(temp_store):
    store.seed_alerts([_alert("DQ-100")])
    store.set_alert_decision("DQ-100", "approved", {"reportDate": "2026-06-25T00:00:00"})

    store.init(temp_store)  # reconnect = restart

    a = store.get_alert("DQ-100")
    assert a["status"] == "approved"
    assert a["triage"]["strDraft"] == {"reportDate": "2026-06-25T00:00:00"}
    assert [x["alertId"] for x in store.list_alerts(status="approved")] == ["DQ-100"]  # index in sync


def test_clear_alerts_empties_the_catalog(temp_store):
    store.seed_alerts([_alert("DQ-100", txns=2)])
    store.clear_alerts()
    assert store.count_alerts() == 0
    assert store.count_transactions() == 0
