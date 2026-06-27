"""The audit trail is stamped in Malaysia time (GMT+8), not the deploy host's UTC."""

from datetime import datetime, timedelta, timezone

from timeutil import LOCAL_TZ, now_local, to_local


def test_now_local_is_gmt8_aware():
    now = now_local()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(hours=8)


def test_to_local_labels_naive_without_shifting_the_clock():
    # Historical stamps were written naive on a GMT+8 build machine: keep the wall clock,
    # just make the zone explicit so the record is unambiguous.
    naive = datetime(2026, 6, 25, 22, 50, 39)
    local = to_local(naive)
    assert local.isoformat() == "2026-06-25T22:50:39+08:00"


def test_to_local_converts_an_aware_utc_instant():
    # A genuinely-UTC instant (e.g. a runtime row from the UTC host) is converted, not relabelled.
    utc = datetime(2026, 6, 25, 14, 50, 39, tzinfo=timezone.utc)
    assert to_local(utc) == datetime(2026, 6, 25, 22, 50, 39, tzinfo=LOCAL_TZ)
