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


def test_reconcile_alerts_inserts_missing_without_touching_existing(temp_store):
    # A durable DB (e.g. Neon) already holds a decided alert; a later deploy ships a catalog with a
    # NEW alert plus a would-be status change to the old one. Reconcile must add the new alert and
    # leave the existing (decided) alert exactly as it is — seed_alerts (seed-only-if-empty) can't.
    store.seed_alerts([_alert("OLD-1", status="approved")])

    store.reconcile_alerts([_alert("OLD-1", status="pending"), _alert("NEW-1", txns=3)])

    assert store.get_alert("OLD-1")["status"] == "approved"  # existing row untouched, not clobbered
    new = store.get_alert("NEW-1")
    assert new is not None and len(new["transactions"]) == 3  # missing alert + its ledger inserted
    assert store.count_alerts() == 2


def test_reconcile_alerts_seeds_an_empty_db(temp_store):
    # Fresh-deploy path: an empty DB gets the whole catalog (insert-missing == insert-all when empty).
    store.reconcile_alerts([_alert("A"), _alert("B")])
    assert store.count_alerts() == 2


def test_clear_alerts_empties_the_catalog(temp_store):
    store.seed_alerts([_alert("DQ-100", txns=2)])
    store.clear_alerts()
    assert store.count_alerts() == 0
    assert store.count_transactions() == 0


def test_seed_cleared_patterns_only_takes_when_empty(temp_store):
    # Slice A demo seed: populates an empty table, but never overwrites session-learned patterns.
    seed = [{"signature": "sig:seed", "typology": "PT-01", "sourceDecisionId": "D1",
             "sourceAlertId": "A1", "clearedCount": 2, "clearedAt": "2026-07-01T09:00:00+08:00"}]
    store.seed_cleared_patterns(seed)
    assert store.find_cleared_pattern("sig:seed")["clearedCount"] == 2

    store.record_clearance("sig:live", "FI-01", "D2", "A2", "2026-07-01T10:00:00+08:00")
    store.seed_cleared_patterns(seed)  # table non-empty now => seed is a no-op
    assert store.find_cleared_pattern("sig:live") is not None  # session pattern survives


def test_seed_purges_obsolete_counterparty_format_patterns(temp_store):
    # A pre-ADR-0021 pattern is keyed on the old counterparty format (cp:<acct>|typ:<code>). The
    # current signature() emits a behavioral envelope (typ=...), so an obsolete row can NEVER match
    # and it silently kills suppression on every alert — while blocking the current-format seed from
    # loading (seed-only-if-empty). Seeding must purge the obsolete row so the current seed governs.
    store.record_clearance("cp:9085912544|typ:PT-01", "PT-01", "SD-00001", "SD-00001",
                           "2026-06-01T09:00:00+08:00")
    seed = [{"signature": "typ=FI-01|amt=4|dir=mix|drain=False|conc=0|xb=0|cash=0|ntxn=5",
             "typology": "FI-01", "sourceDecisionId": "SD-00015", "sourceAlertId": "SD-00015",
             "clearedCount": 1, "clearedAt": "2026-07-01T09:14:00+08:00"}]

    store.seed_cleared_patterns(seed)

    assert store.find_cleared_pattern("cp:9085912544|typ:PT-01") is None  # obsolete purged
    assert store.find_cleared_pattern(seed[0]["signature"]) is not None   # current seed now governs


def test_seed_purge_spares_current_format_session_patterns(temp_store):
    # The purge must be surgical: a current-format session pattern is not obsolete, so it survives a
    # (re)seed and still blocks the demo seed from overwriting real learned memory.
    store.record_clearance("typ=PT-01|amt=3|dir=mix|drain=False|conc=1|xb=0|cash=0|ntxn=3",
                           "PT-01", "DEMO-CL-01", "DEMO-CL-01", "2026-07-02T09:14:00+08:00")
    seed = [{"signature": "typ=FI-01|amt=4|dir=mix|drain=False|conc=0|xb=0|cash=0|ntxn=5",
             "typology": "FI-01", "sourceDecisionId": "SD-00015", "sourceAlertId": "SD-00015",
             "clearedCount": 1, "clearedAt": "2026-07-01T09:14:00+08:00"}]

    store.seed_cleared_patterns(seed)

    assert store.find_cleared_pattern("typ=PT-01|amt=3|dir=mix|drain=False|conc=1|xb=0|cash=0|ntxn=3") is not None
    assert store.find_cleared_pattern(seed[0]["signature"]) is None  # table non-empty => seed no-op


def test_record_clearance_increments_in_place_and_survives_restart(temp_store):
    # Slice A: re-dismissing the same signature bumps clearedCount (idempotent), not duplicate rows,
    # and the learned pattern survives a restart (reconnect to the same db file).
    store.record_clearance("sig:acme", "FI-01", "A-1", "A-1", "2026-07-02T09:14:00+08:00")
    store.record_clearance("sig:acme", "FI-01", "A-2", "A-2", "2026-07-02T10:14:00+08:00")

    store.init(temp_store)  # reconnect = restart

    assert store.find_cleared_pattern("sig:acme") == {
        "signature": "sig:acme",
        "typology": "FI-01",
        "sourceDecisionId": "A-2",
        "sourceAlertId": "A-2",
        "clearedCount": 2,
        "clearedAt": "2026-07-02T10:14:00+08:00",
    }
