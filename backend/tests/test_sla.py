"""STR filing-SLA tests (BNM next-working-day rule).

Anchor dates: 2026-01-01 is a Thursday, so 2026-01-05 is a Monday. From there:
  Mon 01-05 · Wed 01-07 · Thu 01-08 · Fri 01-09 · Sat 01-10 · Mon 01-12 · Tue 01-13.
The working-day logic takes the MY holiday set as an argument, so these tests never
depend on the real calendar (that is loaded and injected at serve time).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sla import CITATION, filing_sla, next_working_day

GMT8 = timezone(timedelta(hours=8))


def _at(y: int, m: int, d: int, hh: int = 9) -> datetime:
    return datetime(y, m, d, hh, 0, tzinfo=GMT8)


# --- next_working_day ---------------------------------------------------------------

def test_weekday_rolls_to_the_next_day():
    start = date(2026, 1, 7)  # Wednesday
    assert start.weekday() == 2
    assert next_working_day(start, set()) == date(2026, 1, 8)


def test_friday_rolls_over_the_weekend_to_monday():
    start = date(2026, 1, 9)  # Friday
    assert start.weekday() == 4
    assert next_working_day(start, set()) == date(2026, 1, 12)


def test_starting_on_a_saturday_rolls_to_monday():
    start = date(2026, 1, 10)  # Saturday
    assert start.weekday() == 5
    assert next_working_day(start, set()) == date(2026, 1, 12)


def test_a_monday_holiday_pushes_to_tuesday():
    start = date(2026, 1, 9)  # Friday
    holidays = {date(2026, 1, 12)}  # the Monday is a public holiday
    assert next_working_day(start, holidays) == date(2026, 1, 13)


def test_skips_a_holiday_that_abuts_the_weekend():
    start = date(2026, 1, 8)  # Thursday
    holidays = {date(2026, 1, 9)}  # Friday holiday, then Sat/Sun
    assert next_working_day(start, holidays) == date(2026, 1, 12)


# --- filing_sla ---------------------------------------------------------------------

def test_dismissed_alert_has_no_filing_obligation():
    sla = filing_sla(
        recommendation="escalate",
        final_disposition="dismiss",
        established_at=_at(2026, 1, 7),
        now=_at(2026, 1, 7),
        holidays=set(),
    )
    assert sla["applicable"] is False
    assert sla["state"] == "notApplicable"
    assert sla["dueBy"] is None
    assert sla["citation"] == CITATION


def test_escalated_decision_starts_a_live_clock_to_the_next_working_day():
    established = _at(2026, 1, 7, 14)  # Wednesday afternoon
    sla = filing_sla(
        recommendation="escalate",
        final_disposition="escalate",
        established_at=established,
        now=_at(2026, 1, 7, 15),
        holidays=set(),
    )
    assert sla["applicable"] is True
    assert sla["state"] == "active"
    assert sla["dueBy"] == "2026-01-08"  # Thursday
    assert sla["establishedAt"] == established.isoformat()


def test_pending_escalate_recommendation_shows_a_prospective_deadline():
    sla = filing_sla(
        recommendation="escalate",
        final_disposition=None,
        established_at=None,
        now=_at(2026, 1, 9),  # Friday
        holidays=set(),
    )
    assert sla["applicable"] is True
    assert sla["state"] == "prospective"
    assert sla["dueBy"] == "2026-01-12"  # Monday
    assert sla["establishedAt"] is None


def test_pending_dismiss_recommendation_is_not_applicable():
    sla = filing_sla(
        recommendation="dismiss",
        final_disposition=None,
        established_at=None,
        now=_at(2026, 1, 9),
        holidays=set(),
    )
    assert sla["applicable"] is False
    assert sla["state"] == "notApplicable"


def test_a_past_deadline_reads_as_overdue():
    sla = filing_sla(
        recommendation="escalate",
        final_disposition="escalate",
        established_at=_at(2026, 1, 5, 9),   # Monday
        now=_at(2026, 1, 9, 9),              # Friday — well past the Tuesday deadline
        holidays=set(),
    )
    assert sla["dueBy"] == "2026-01-06"  # Tuesday
    assert sla["state"] == "overdue"
