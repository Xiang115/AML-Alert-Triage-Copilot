"""Local wall-clock time for the accountability trail.

The bank operates in Malaysia (BNM); analysts and a regulator replaying the audit trail
read it in local time — GMT+8, no DST — not the deployment host's UTC (Render runs UTC, which
surfaced as "UK time" on the live console). A fixed offset avoids a zoneinfo/tzdata dependency
on the host. Stamped timestamps are timezone-aware, so their ISO form carries the explicit
+08:00 offset — the time is then unambiguous in the stored record and on goAML export.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Asia/Kuala_Lumpur — GMT+8 year-round (no daylight saving). Fixed offset, no tzdata needed.
LOCAL_TZ = timezone(timedelta(hours=8))


def now_local() -> datetime:
    """Current time as a timezone-aware GMT+8 datetime — the stamp for every audit event."""
    return datetime.now(LOCAL_TZ)


def to_local(dt: datetime) -> datetime:
    """Re-express `dt` in GMT+8.

    A naive datetime is assumed to already be local wall-clock time: the historical audit
    stamps were written by `datetime.now()` on a GMT+8 build machine without a zone, so it is
    *labelled* GMT+8 without shifting the clock. An aware datetime is converted to GMT+8.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)
