"""SQLAlchemy-backed persistence for the analyst's Decisions and the audit trail.

The accountability record a regulator can replay must survive a restart, be safe under
concurrent requests, and scale to a bank's alert volume — so it lives in a real SQL
database behind a single `DATABASE_URL` seam. The demo runs on SQLite (zero-ops); a
production deployment points the URL at Postgres or MySQL with **no code change** — the
same swap the LLM client (`llm.py`) makes for the model provider:

    sqlite:///.../data/app.db                  (demo default)
    postgresql+psycopg://user:pw@host/db       (production)

Four tables:
  alerts        one row per alert (metadata + embedded triage) — the input catalog.
  transactions  one row per ledger entry (indexed by alert_id) — the table that grows
                to a bank's volume.
  decisions     one row per alert: the CURRENT disposition (last write wins) — the source
                of truth for the STR filing gate.
  audit         append-only event log (autoClear / debateResolved seed + decision /
                submission events), ordered by an autoincrement key.

Built on SQLAlchemy Core (not the ORM) so the SQL stays explicit and the surface tiny;
the engine's connection pool makes concurrent requests safe and the schema is emitted
dialect-correctly per database. Payloads are the exact camelCase JSON dicts the API
emits, so a store round-trip is the identity — the wire contract stays the one shape.
"""

from __future__ import annotations

import json

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

import config

_metadata = MetaData()

decisions = Table(
    "decisions",
    _metadata,
    Column("alert_id", String(64), primary_key=True),
    Column("payload", Text, nullable=False),
)

audit = Table(
    "audit",
    _metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),  # SERIAL on PG, rowid on SQLite
    Column("payload", Text, nullable=False),
)

# Slice A: learned cross-customer suppression patterns, keyed by a normalized
# behavioral-envelope signature. record_clearance() upserts on a human dismiss.
cleared_patterns = Table(
    "cleared_patterns",
    _metadata,
    Column("signature", String(160), primary_key=True),
    Column("typology", String(32), nullable=True),
    Column("source_decision_id", String(64), nullable=False),
    Column("source_alert_id", String(64), nullable=False),
    Column("cleared_count", Integer, nullable=False),
    Column("cleared_at", String(40), nullable=False),
)

# Input data: the alert catalog. One row per alert (metadata + embedded triage) and one
# row per ledger transaction — the relational, queryable, scalable home for the alerts the
# pipeline reasons over (vs. the file-of-record results.json). status/routing are indexed
# columns so the queue filters are real WHERE clauses; the transactions table is the one
# that grows to a bank's volume, indexed by alert_id.
alerts = Table(
    "alerts",
    _metadata,
    Column("alert_id", String(64), primary_key=True),
    Column("status", String(16), nullable=False, index=True),
    Column("routing", String(16), nullable=True, index=True),
    Column("payload", Text, nullable=False),  # the Alert dict WITHOUT transactions
)

transactions = Table(
    "transactions",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),  # surrogate: txn ids need not be global
    Column("transaction_id", String(64), nullable=False, index=True),
    Column("alert_id", String(64), nullable=False, index=True),
    Column("seq", Integer, nullable=False),  # preserves ledger order
    Column("payload", Text, nullable=False),  # the Transaction dict
)

copilot_runs = Table(
    "copilot_runs",
    _metadata,
    Column("run_id", String(64), primary_key=True),
    Column("alert_id", String(64), nullable=False, index=True),
    Column("started_at", String(40), nullable=False, index=True),
    Column("payload", Text, nullable=False),
)

qa_outcomes = Table(
    "qa_outcomes",
    _metadata,
    Column("alert_id", String(64), primary_key=True),
    Column("reviewed_at", String(40), nullable=False, index=True),
    Column("payload", Text, nullable=False),
)

governance_changes = Table(
    "governance_changes",
    _metadata,
    Column("change_id", String(64), primary_key=True),
    Column("status", String(32), nullable=False, index=True),
    Column("requested_at", String(40), nullable=False, index=True),
    Column("payload", Text, nullable=False),
)

_engine: Engine | None = None
_seed: list[dict] = []  # remembered so reset() can restore the Queue Agent's audit trail
_alert_seed: list[dict] = []  # remembered so reset() can restore the alert catalog
_cleared_seed: list[dict] = []  # remembered so reset() can restore the demo suppression patterns


def _is_memory_sqlite(url: str) -> bool:
    return url.startswith("sqlite") and (url == "sqlite://" or ":memory:" in url)


def init(url: str | None = None) -> None:
    """Open the engine for `url` (defaults to config.DATABASE_URL) and ensure the tables
    exist. Idempotent; safe to call at import and to call again to point at a new DB."""
    global _engine
    url = url or config.DATABASE_URL
    kwargs: dict = {}
    if _is_memory_sqlite(url):
        # Keep one connection so an in-memory SQLite db survives across the pool (tests).
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    elif url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    _engine = create_engine(url, **kwargs)
    _metadata.create_all(_engine)


def _require() -> Engine:
    if _engine is None:
        init()
    assert _engine is not None
    return _engine


def seed_audit(entries: list[dict]) -> None:
    """Seed the audit trail with the Queue Agent's precomputed events (ADR-0010/0011),
    but ONLY if it is empty — so a restart preserves the persisted runtime events instead
    of duplicating the seed. Remembers the seed so reset() can restore it."""
    global _seed
    _seed = list(entries)
    eng = _require()
    with eng.begin() as conn:
        count = conn.execute(select(func.count()).select_from(audit)).scalar_one()
        if count == 0 and _seed:
            conn.execute(insert(audit), [{"payload": json.dumps(e)} for e in _seed])


def record_decision(alert_id: str, payload: dict) -> None:
    """Upsert the current decision for an alert (the filing gate reads this). Portable
    delete-then-insert in one transaction — atomic, and dialect-agnostic."""
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(decisions).where(decisions.c.alert_id == alert_id))
        conn.execute(insert(decisions), {"alert_id": alert_id, "payload": json.dumps(payload)})


def get_decision(alert_id: str) -> dict | None:
    eng = _require()
    with eng.connect() as conn:
        row = conn.execute(
            select(decisions.c.payload).where(decisions.c.alert_id == alert_id)
        ).first()
    return json.loads(row[0]) if row else None


def all_decisions() -> list[dict]:
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(select(decisions.c.payload)).all()
    return [json.loads(r[0]) for r in rows]


def append_audit(entry: dict) -> None:
    eng = _require()
    with eng.begin() as conn:
        conn.execute(insert(audit), {"payload": json.dumps(entry)})


def all_audit() -> list[dict]:
    """Every audit event in insertion order (oldest first); the API reverses for display."""
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(select(audit.c.payload).order_by(audit.c.seq)).all()
    return [json.loads(r[0]) for r in rows]


def record_copilot_run(payload: dict) -> None:
    """Persist a captured live copilot run ledger for later audit replay."""
    eng = _require()
    with eng.begin() as conn:
        conn.execute(insert(copilot_runs), {
            "run_id": payload["runId"],
            "alert_id": payload["alertId"],
            "started_at": payload["startedAt"],
            "payload": json.dumps(payload),
        })


def list_copilot_runs(alert_id: str) -> list[dict]:
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(
            select(copilot_runs.c.payload)
            .where(copilot_runs.c.alert_id == alert_id)
            .order_by(copilot_runs.c.started_at.desc())
        ).all()
    return [json.loads(r[0]) for r in rows]


def get_copilot_run(alert_id: str, run_id: str) -> dict | None:
    eng = _require()
    with eng.connect() as conn:
        row = conn.execute(
            select(copilot_runs.c.payload)
            .where(copilot_runs.c.alert_id == alert_id)
            .where(copilot_runs.c.run_id == run_id)
        ).first()
    return json.loads(row[0]) if row else None


def record_qa_outcome(payload: dict) -> None:
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(qa_outcomes).where(qa_outcomes.c.alert_id == payload["alertId"]))
        conn.execute(insert(qa_outcomes), {
            "alert_id": payload["alertId"],
            "reviewed_at": payload["reviewedAt"],
            "payload": json.dumps(payload),
        })


def get_qa_outcome(alert_id: str) -> dict | None:
    eng = _require()
    with eng.connect() as conn:
        row = conn.execute(
            select(qa_outcomes.c.payload).where(qa_outcomes.c.alert_id == alert_id)
        ).first()
    return json.loads(row[0]) if row else None


def all_qa_outcomes() -> list[dict]:
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(select(qa_outcomes.c.payload).order_by(qa_outcomes.c.reviewed_at.desc())).all()
    return [json.loads(r[0]) for r in rows]


def record_governance_change(payload: dict) -> None:
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(governance_changes).where(governance_changes.c.change_id == payload["changeId"]))
        conn.execute(insert(governance_changes), {
            "change_id": payload["changeId"],
            "status": payload["status"],
            "requested_at": payload["requestedAt"],
            "payload": json.dumps(payload),
        })


def all_governance_changes() -> list[dict]:
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(
            select(governance_changes.c.payload).order_by(governance_changes.c.requested_at.desc())
        ).all()
    return [json.loads(r[0]) for r in rows]


# Timestamp fields stamped into stored payloads — the audit trail's `at`, and the decision
# record's `decidedAt` / `submittedAt`. Migrated to GMT+8 by migrate_timestamps_to_local().
_TS_FIELDS = ("at", "decidedAt", "submittedAt")


def migrate_timestamps_to_local() -> int:
    """Relabel every stored timestamp in the GMT+8 local zone (see timeutil.to_local), so the
    accountability trail reads in Malaysia time instead of the UTC the deploy host stamped.
    Idempotent — a value that already carries a UTC offset is left untouched, so re-running
    (or running against an already-migrated DB) is a no-op. Returns the number of rows
    rewritten. Reusable for a persistent Postgres deploy; the demo's ephemeral SQLite reseeds
    from the GMT+8 artifacts instead."""
    from datetime import datetime

    from timeutil import to_local

    def _convert(payload: str) -> str | None:
        d = json.loads(payload)
        changed = False
        for field in _TS_FIELDS:
            val = d.get(field)
            if not isinstance(val, str):
                continue
            try:
                parsed = datetime.fromisoformat(val)
            except ValueError:
                continue
            local = to_local(parsed).isoformat()
            if local != val:
                d[field] = local
                changed = True
        return json.dumps(d) if changed else None

    eng = _require()
    rewritten = 0
    with eng.begin() as conn:
        for tbl, key in ((audit, audit.c.seq), (decisions, decisions.c.alert_id)):
            for row in conn.execute(select(key, tbl.c.payload)).all():
                new = _convert(row[1])
                if new is not None:
                    conn.execute(update(tbl).where(key == row[0]).values(payload=new))
                    rewritten += 1
    return rewritten


# --- Slice A: cross-customer self-learning suppression -----------------------------

def seed_cleared_patterns(patterns: list[dict]) -> None:
    """Seed the learned-suppression patterns (demo initial state — prior clearances the team made),
    but ONLY if the table is empty, so a restart keeps session-learned patterns. Remembers the seed
    so reset() restores it. Each dict is camelCase: signature, typology, sourceDecisionId,
    sourceAlertId, clearedCount, clearedAt."""
    global _cleared_seed
    _cleared_seed = list(patterns)
    eng = _require()
    with eng.begin() as conn:
        count = conn.execute(select(func.count()).select_from(cleared_patterns)).scalar_one()
        if count == 0 and _cleared_seed:
            conn.execute(insert(cleared_patterns), [
                {"signature": p["signature"], "typology": p.get("typology"),
                 "source_decision_id": p["sourceDecisionId"], "source_alert_id": p["sourceAlertId"],
                 "cleared_count": p["clearedCount"], "cleared_at": p["clearedAt"]}
                for p in _cleared_seed
            ])


def record_clearance(
    signature: str,
    typology: str,
    source_decision_id: str,
    source_alert_id: str,
    cleared_at: str,
) -> None:
    """Atomically upsert a learned suppression pattern keyed by its normalized signature."""
    eng = _require()
    with eng.begin() as conn:
        updated = conn.execute(
            update(cleared_patterns)
            .where(cleared_patterns.c.signature == signature)
            .values(
                cleared_count=cleared_patterns.c.cleared_count + 1,
                cleared_at=cleared_at,
                source_decision_id=source_decision_id,
                source_alert_id=source_alert_id,
            )
        )
        if updated.rowcount:
            return
        try:
            conn.execute(
                insert(cleared_patterns),
                {
                    "signature": signature,
                    "typology": typology,
                    "source_decision_id": source_decision_id,
                    "source_alert_id": source_alert_id,
                    "cleared_count": 1,
                    "cleared_at": cleared_at,
                },
            )
        except IntegrityError:
            # Another request inserted the same signature after our update miss; retry as an increment.
            conn.execute(
                update(cleared_patterns)
                .where(cleared_patterns.c.signature == signature)
                .values(
                    cleared_count=cleared_patterns.c.cleared_count + 1,
                    cleared_at=cleared_at,
                    source_decision_id=source_decision_id,
                    source_alert_id=source_alert_id,
                )
            )


def find_cleared_pattern(signature: str) -> dict | None:
    eng = _require()
    with eng.connect() as conn:
        row = conn.execute(
            select(
                cleared_patterns.c.signature,
                cleared_patterns.c.typology,
                cleared_patterns.c.source_decision_id,
                cleared_patterns.c.source_alert_id,
                cleared_patterns.c.cleared_count,
                cleared_patterns.c.cleared_at,
            ).where(cleared_patterns.c.signature == signature)
        ).first()
    if row is None:
        return None
    return {
        "signature": row[0],
        "typology": row[1],
        "sourceDecisionId": row[2],
        "sourceAlertId": row[3],
        "clearedCount": row[4],
        "clearedAt": row[5],
    }


def all_cleared_patterns() -> list[dict]:
    """All learned suppression patterns, newest first."""
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(
            select(
                cleared_patterns.c.signature,
                cleared_patterns.c.typology,
                cleared_patterns.c.source_alert_id,
                cleared_patterns.c.cleared_count,
                cleared_patterns.c.cleared_at,
            ).order_by(cleared_patterns.c.cleared_at.desc())
        ).all()
    return [
        {
            "signature": row[0],
            "typology": row[1],
            "sourceAlertId": row[2],
            "clearedCount": row[3],
            "clearedAt": row[4],
        }
        for row in rows
    ]


# --- alert catalog: input data (alerts + their transactions) ----------------------

def seed_alerts(alert_dicts: list[dict]) -> None:
    """Idempotent ingest of the alert catalog into the DB: split each alert into its
    metadata row + one transaction row per ledger entry. Only seeds an empty table, so a
    restart keeps decision-updated statuses. Remembers the catalog so reset() restores it."""
    global _alert_seed
    _alert_seed = list(alert_dicts)
    eng = _require()
    with eng.begin() as conn:
        count = conn.execute(select(func.count()).select_from(alerts)).scalar_one()
        if count == 0:
            for a in _alert_seed:
                _insert_alert(conn, a)


def _insert_alert(conn, a: dict) -> None:
    meta = {k: v for k, v in a.items() if k != "transactions"}
    conn.execute(
        insert(alerts),
        {"alert_id": a["alertId"], "status": a["status"],
         "routing": a.get("routing"), "payload": json.dumps(meta)},
    )
    txns = a.get("transactions") or []
    if txns:
        conn.execute(
            insert(transactions),
            [{"transaction_id": t["transactionId"], "alert_id": a["alertId"],
              "seq": i, "payload": json.dumps(t)} for i, t in enumerate(txns)],
        )


def clear_alerts() -> None:
    """Drop the alert catalog (transactions first, then alerts). Used by the ingest CLI's
    --reset; reset() re-seeds afterwards."""
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(transactions))
        conn.execute(delete(alerts))


def list_alerts(status: str | None = None, routing: str | None = None) -> list[dict]:
    """The queue: alert metadata (no transactions), filtered on the indexed status/routing
    columns — the production query path. Each returned alert carries transactions=None."""
    eng = _require()
    stmt = select(alerts.c.payload)
    if status is not None:
        stmt = stmt.where(alerts.c.status == status)
    if routing is not None:
        stmt = stmt.where(alerts.c.routing == routing)
    with eng.connect() as conn:
        rows = conn.execute(stmt).all()
    out = []
    for (payload,) in rows:
        a = json.loads(payload)
        a["transactions"] = None  # queue omits embedded transactions
        out.append(a)
    return out


def get_alert(alert_id: str) -> dict | None:
    """Alert detail: metadata + its transactions in ledger order. None if absent."""
    eng = _require()
    with eng.connect() as conn:
        row = conn.execute(
            select(alerts.c.payload).where(alerts.c.alert_id == alert_id)
        ).first()
        if row is None:
            return None
        a = json.loads(row[0])
        txn_rows = conn.execute(
            select(transactions.c.payload)
            .where(transactions.c.alert_id == alert_id)
            .order_by(transactions.c.seq)
        ).all()
    a["transactions"] = [json.loads(t[0]) for t in txn_rows]
    return a


def set_alert_decision(alert_id: str, status: str, str_draft: dict | None) -> None:
    """Persist a decision's effect on the alert row: the new status + resolved STR draft, so
    a restart preserves them with no separate replay step."""
    eng = _require()
    with eng.begin() as conn:
        row = conn.execute(
            select(alerts.c.payload).where(alerts.c.alert_id == alert_id)
        ).first()
        if row is None:
            return
        a = json.loads(row[0])
        a["status"] = status
        a["triage"]["strDraft"] = str_draft
        conn.execute(
            update(alerts).where(alerts.c.alert_id == alert_id)
            .values(status=status, payload=json.dumps(a))
        )


def count_alerts() -> int:
    eng = _require()
    with eng.connect() as conn:
        return conn.execute(select(func.count()).select_from(alerts)).scalar_one()


def count_transactions() -> int:
    eng = _require()
    with eng.connect() as conn:
        return conn.execute(select(func.count()).select_from(transactions)).scalar_one()


def reset() -> None:
    """Wipe all session state and restore the seeds — the persistence-layer equivalent of
    the demo /reset and the per-test isolation hook. Decisions + audit events are dropped;
    the alert catalog and the Queue Agent's audit seed are restored."""
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(decisions))
        conn.execute(delete(audit))
        conn.execute(delete(cleared_patterns))  # Slice A: drop learned suppression patterns
        conn.execute(delete(copilot_runs))
        conn.execute(delete(qa_outcomes))
        conn.execute(delete(governance_changes))
        conn.execute(delete(transactions))
        conn.execute(delete(alerts))
    seed_audit(_seed)                     # re-insert the remembered audit seed
    seed_alerts(_alert_seed)              # re-insert the remembered alert catalog
    seed_cleared_patterns(_cleared_seed)  # re-insert the remembered suppression patterns
